<!--
title: AgentOps Redux
description: Production-ready Databricks AgentOps framework — from dev to prod with CI/CD, evaluation, and observability
category: framework
tags: [agentops, databricks, mlflow, langchain, CI/CD, RAG, evaluation]
related_docs:
  - docs/intro.md
  - docs/architecture.md
  - docs/deployment.md
  - CLAUDE.md
-->

# AgentOps Redux

> **The opinionated, production-ready framework for developing, evaluating, and promoting AI agents on Databricks.**

AgentOps Redux is the spiritual successor to MLOps Stacks for the agentic era. It provides a lean, deployable best-practice framework for getting agents into production on the Databricks platform — with full CI/CD, MLflow observability, Unity Catalog governance, and automated evaluation gates at every stage.

AgentOps Redux is **AI coding platform-native**. It ships a shared MCP server and platform-specific context files for Claude Code, Cursor, Windsurf, and OpenAI Codex so any of these tools can deploy, scaffold, evaluate, and monitor agents without manual setup.

---

## Why AgentOps Redux

Most teams building agents struggle with the same problems:

- No consistent pattern for dev → staging → prod promotion
- Evaluation happens ad-hoc, not at every promotion gate
- No observability into what agents are doing in production
- Tool sprawl: notebooks, scripts, and framework code scattered with no cohesion

AgentOps Redux solves these with an opinionated, Databricks-native framework that is simple enough to understand and extend, but rigorous enough to trust in production.

It also ships first-class support for AI coding tools (Claude Code, Cursor, Windsurf, Codex) — see [AI Coding Platform Integration](#ai-coding-platform-integration).

---

## Architecture

![AgentOps Multi-Environment Single-Account Multi-Agent View](pics/AgentOps%20Multi-Environment%20Single-Account%20Multi-Agent%20View.png)

```
Git Branch         dev ──────────────── main ─────────── release
                    │   CI trigger         │   Merge          │   CD deploy
                    ▼                      ▼                   ▼
Workspace      Development           Staging             Production
               ├─ Data Prep          ├─ Unit Tests       ├─ App Deploy
               ├─ Agent Dev          ├─ Integration      ├─ Batch Infer
               ├─ Evaluation         └─ Validation       └─ Monitoring
               └─ App Deploy
                    │                      │                   │
                    └──────────────────────┴───────────────────┘
                                      Unity Catalog
                              Dev Catalog (r/w) │ Prod Catalog (read-only from dev)
```

**Core principle**: Branch = Environment. Promoting code = merging branches. No manual deploy steps.

### Technology Stack

| Component | Technology |
|---|---|
| Agent base class | `mlflow.pyfunc.PythonModel` |
| LLM calls | Databricks Foundation Model API via `databricks-langchain` |
| Retrieval | Databricks Vector Search (ANN, hybrid, + `DatabricksReranker`) |
| Embeddings | Databricks BGE Large (`databricks-bge-large-en`) |
| Evaluation | `mlflow.genai.evaluate()` with Correctness, Groundedness, Relevance, Safety scorers |
| Tracing | `mlflow.trace` + `mlflow.langchain.autolog()` |
| Governance | Unity Catalog (models, tools, data) |
| Deployment | Databricks Model Serving + AI Gateway (guardrails, rate limits) |
| Infrastructure | Databricks Asset Bundles |
| CI/CD | GitHub Actions |
| AI agent tooling | FastMCP server + Claude Code, Cursor, Windsurf, Codex context files |

See [Architecture Reference](docs/architecture.md) for the full breakdown.

---

## Quick Start

### Prerequisites

- Databricks workspace with Unity Catalog enabled
- Databricks CLI >= 0.219.0
- Python 3.11+

### 1. Configure workspace credentials

```bash
databricks configure
```

### 2. Build the wheel and deploy to dev

```bash
pip install build
python -m build          # creates dist/agentops_framework-*.whl (required by DAB workflows)
python scripts/deploy.py --target dev
```

### 3. Verify deployment

```bash
python scripts/verify.py --target dev --test-inference
```

### 4. Run evaluation

```bash
python reference_agent/eval/run_eval.py --sample 5
```

---

## Project Structure

```
agentops-redux/
│
├── databricks.yml                     # DAB root — bundle name, variables, includes
│
├── bundle/
│   ├── resources/                     # One YAML per DAB workflow
│   │   ├── data_preparation_workflow.yml
│   │   ├── agent_development_workflow.yml
│   │   ├── app_deployment_workflow.yml
│   │   ├── batch_inferencing_workflow.yml
│   │   └── monitoring_workflow.yml    # Nightly online evaluation
│   └── targets/
│       ├── dev.yml                    # Dev workspace vars + defaults
│       ├── staging.yml                # Staging workspace vars
│       └── prod.yml                   # Prod vars: guardrails on, hybrid+reranking, no scale-to-zero
│
├── framework/                         # Reusable Python library (installable wheel)
│   ├── config.py                      # AgentOpsConfig — single source of truth
│   ├── entrypoints.py                 # Console scripts for all DAB python_wheel_task entry points
│   ├── agent_development/
│   │   ├── agent_base.py              # AgentBase(mlflow.pyfunc.PythonModel) — all agents inherit this
│   │   ├── router.py                  # AgentRouter — multi-agent intent routing
│   │   └── tool_registry.py          # Unity Catalog function/tool registration
│   ├── data_preparation/
│   │   ├── ingestion.py               # DataIngestionBase + DeltaTableIngestion
│   │   ├── chunking.py                # RecursiveCharacterChunker, SemanticChunker
│   │   ├── vector_search_indexing.py  # VectorSearchIndexer (Delta Sync)
│   │   └── unstructured/              # ai_parse_document, ai_query_extraction wrappers
│   ├── evaluation/
│   │   ├── evaluator.py               # AgentEvaluator + EvaluationThresholds
│   │   ├── online_evaluator.py        # OnlineEvaluator — scores live production traces
│   │   ├── metrics.py                 # Custom scorer definitions
│   │   └── dataset.py                 # Eval dataset management
│   ├── deployment/
│   │   ├── deploy_agent.py            # UC model registration + @champion alias
│   │   └── deploy_app.py              # AppDeployer: endpoint create/update, AI Gateway, canary
│   ├── batch_inferencing/
│   │   └── batch_inferencer.py        # Spark-based batch inference via Model Serving REST API
│   └── utils/
│       ├── mlflow_utils.py            # Experiment setup, autologging, cost tracking
│       ├── unity_catalog.py           # Catalog/schema helpers, UC permissions
│       └── databricks_utils.py        # SDK wrappers (workspace, secrets, jobs)
│
├── reference_agent/                   # Complete working multi-agent RAG application
│   ├── agents/
│   │   ├── agent1/
│   │   │   ├── agent.py               # RAGAgent: ANN/hybrid search, DatabricksReranker
│   │   │   └── tools.py               # UC-registered tools: get_document_metadata, get_related_chunks
│   │   └── agent2/
│   │       ├── agent.py               # SummarizationAgent
│   │       └── tools.py               # UC-registered tools: get_document_for_summary, count_words
│   ├── router/
│   │   └── router.py                  # Keyword fast-path + LLM classification routing
│   ├── eval/
│   │   ├── eval_dataset.jsonl         # ~75 labelled Q&A + summarization pairs
│   │   └── run_eval.py                # CLI: run mlflow.genai.evaluate() for both agents
│   ├── data/sample_documents/         # Sample HR, policy, and technical support docs
│   └── app.py                         # mlflow.pyfunc.PythonModel wrapping the router
│
├── tests/
│   ├── unit/                          # Pure Python, no Databricks — run anywhere
│   │   ├── test_chunking.py
│   │   ├── test_router.py
│   │   ├── test_tool_registry.py
│   │   └── test_evaluator.py
│   ├── integration/                   # Requires DATABRICKS_HOST + staging credentials
│   │   ├── test_vector_search.py
│   │   ├── test_tool_invocation.py
│   │   └── test_mlflow_logging.py
│   └── validation/                    # Full eval gate — run in staging CI
│       ├── test_agent_quality.py
│       └── conftest.py
│
├── scripts/
│   ├── deploy.py                      # CLI: databricks bundle deploy wrapper
│   ├── scaffold.py                    # CLI: generate new agent from templates
│   ├── verify.py                      # CLI: live health checks → verification_report.md
│   └── generate_manifest.py           # CLI: post-deploy → deployment_manifest.md
│
├── templates/
│   ├── agent/
│   │   ├── agent.py.tmpl              # Agent class template
│   │   └── tools.py.tmpl              # UC tools template
│   └── workflow/
│       └── agent_workflow.yml.tmpl    # DAB workflow YAML template
│
├── skills/                            # Claude Code slash commands (install as plugin)
│   ├── skill_manifest.json
│   ├── deploy-framework.md            # /deploy-agentops
│   ├── scaffold-agent.md              # /scaffold-agent
│   ├── run-eval.md                    # /run-eval
│   ├── read-manifest.md               # /read-manifest
│   └── monitor-deployment.md          # /monitor-deployment
│
├── agentops_mcp/                      # MCP server for AI agent integration
│   ├── server.py                      # FastMCP server (7 tools)
│   └── tools/
│       ├── deploy.py
│       ├── scaffold.py
│       ├── eval.py
│       ├── manifest.py
│       ├── monitor.py
│       └── feedback.py                # submit_trace_feedback, export_negative_traces
│
├── .github/workflows/
│   ├── ci.yml                         # Trigger: push to dev → unit+integration+validation tests
│   └── cd.yml                         # Trigger: push to release → bundle deploy prod
│
├── docs/                              # AI-agent-ready documentation
├── deployment_manifest.md             # Auto-generated post-deploy (do not edit by hand)
├── CLAUDE.md                          # Agent context: Claude Code
├── AGENTS.md                          # Agent context: OpenAI Codex
├── .windsurfrules                     # Agent context: Windsurf
├── .cursor/
│   ├── rules/agentops.mdc             # Agent context: Cursor (alwaysApply)
│   └── mcp.json                       # Cursor MCP pre-configuration (zero setup)
├── .windsurf/
│   └── mcp.json                       # Windsurf MCP pre-configuration (zero setup)
└── pyproject.toml                     # Package config + [project.scripts] for DAB entry points
```

---

## Key Concepts

### Branch = Environment

| Branch | Workspace | Triggered By |
|---|---|---|
| `dev` | Development | Developer push |
| `main` | Staging | CI merge after tests pass |
| `release` | Production | CD pipeline on release merge |

### DAB Workflows

Five Databricks Asset Bundle workflows, each with a distinct role:

| Workflow | Environment | Purpose |
|---|---|---|
| `data_preparation_workflow` | dev | Ingest → chunk → index into Vector Search |
| `agent_development_workflow` | dev | Build agents, register UC tools, run eval gate |
| `app_deployment_workflow` | dev + prod | Package agents, deploy Model Serving endpoint |
| `batch_inferencing_workflow` | prod | Scheduled offline inference via Model Serving REST API |
| `monitoring_workflow` | prod | Nightly online evaluation from live production traces |

### Evaluation Gates

Every agent must pass before promotion:

| Metric | Dev threshold | Staging → Prod gate |
|---|---|---|
| Correctness | ≥ 0.80 | ≥ 0.90 |
| Groundedness | ≥ 0.90 | ≥ 0.95 |
| Relevance | ≥ 0.80 | ≥ 0.85 |
| Safety | 1.00 | 1.00 |

### Bundle Variables: Dev vs Prod

Key variables that differ across targets:

| Variable | Dev default | Prod override |
|---|---|---|
| `query_type` | `ann` | `hybrid` |
| `enable_reranking` | `false` | `true` |
| `reranker_candidates` | `20` | `30` |
| `enable_guardrails` | `false` | `true` |
| `rate_limit_per_minute` | `0` (off) | `120` |
| `endpoint_workload_size` | `Small` | `Medium` |
| `endpoint_scale_to_zero` | `true` | `false` |

---

## What's Built In

### RAG Agent (Agent 1)

Three retrieval modes, selectable via bundle variables:

| Mode | Config | When to use |
|---|---|---|
| Semantic (ANN) | `query_type=ann` (default) | General Q&A |
| Hybrid | `query_type=hybrid` | Exact names, IDs, acronyms |
| Hybrid + Reranking | `query_type=hybrid, enable_reranking=true` | Highest precision (prod default) |

Hybrid uses BM25 + semantic vector similarity. Reranking uses the native `DatabricksReranker` — fetches `reranker_candidates` results, then re-scores and trims to `num_retrieved_chunks` before the LLM.

Metadata filtering is also supported per-call:

```python
agent = RAGAgent(
    query_type="hybrid",
    enable_reranking=True,
    metadata_filter={"category": {"LIKE": "policy%"}},
)
```

### AI Gateway (Guardrails + Rate Limiting)

Enabled automatically on the prod endpoint via `app_deployment_workflow`:

```python
deployer.deploy(
    model_name="agentops_prod.agentops.multi_agent_app",
    enable_guardrails=True,    # PII blocking + input/output safety filtering
    rate_limit_per_minute=120,
)
```

### Canary Deployments

Roll out a new model version to a fraction of traffic before full promotion:

```python
# Deploy with 10% traffic to challenger version
result = deployer.deploy(..., enable_canary=True, canary_traffic_percentage=10)

# After soak period: promote challenger to 100%
deployer.promote_canary()
```

### Online Evaluation (Production Monitoring)

The `monitoring_workflow` nightly job samples recent MLflow traces and re-scores them without re-invoking the agent:

```python
evaluator = OnlineEvaluator(agent_name="rag_agent", trace_sample_size=50)
result, alerts = evaluator.run()
# Alerts trigger on safety regressions (non-zero exit → DAB email alert)
```

### Cost Tracking

Token usage is captured by `mlflow.langchain.autolog()`. Cost helpers in `framework/utils/mlflow_utils.py` aggregate across traces and log to MLflow:

```python
cost_summary = log_token_cost(traces, model_endpoint=cfg.llm_endpoint)
# Logs: cost.total_cost_usd, cost.avg_cost_per_query_usd, cost.total_prompt_tokens, ...
```

### Human-in-the-Loop Feedback Loop

Attach user or SME feedback to any production trace via the MCP tool:

```python
submit_trace_feedback(trace_id="abc123", feedback="negative",
                      comment="Wrong policy version cited", source="sme_reviewer")
```

Export negatively-rated traces as eval dataset candidates for annotation:

```python
export_negative_traces(experiment_id="...", output_path="reference_agent/eval/hitl_review.jsonl")
```

---

## Adding a New Agent

```bash
python scripts/scaffold.py \
  --name customer_support \
  --description "Handles customer support queries using product docs" \
  --type rag
```

Creates:
- `reference_agent/agents/customer_support/agent.py` — implement `_invoke()` here
- `reference_agent/agents/customer_support/tools.py` — UC tool stubs
- `reference_agent/eval/customer_support_eval_dataset.jsonl` — add labelled examples
- DAB workflow task entries

Then register the agent in `reference_agent/router/router.py`. See [Extension Guide](docs/extension-guide.md) for the full walkthrough.

---

## AI Coding Platform Integration

AgentOps ships a shared MCP server and platform-specific context files for four AI coding platforms. Pick the tool you already use — no framework changes required.

| Platform | MCP Setup | Context File | Setup Required |
|---|---|---|---|
| **Claude Code** | Manual (global config) | `CLAUDE.md` | Add one entry to `~/.claude/claude_desktop_config.json` |
| **Cursor** | Pre-configured (`.cursor/mcp.json`) | `.cursor/rules/agentops.mdc` | Set `DATABRICKS_HOST` + `DATABRICKS_TOKEN` env vars |
| **Windsurf** | Pre-configured (`.windsurf/mcp.json`) | `.windsurfrules` | Set `DATABRICKS_HOST` + `DATABRICKS_TOKEN` env vars |
| **OpenAI Codex** | Manual (Codex MCP config) | `AGENTS.md` | Add one entry to your Codex MCP configuration |

All platforms share the same 7 MCP tools. Context files are kept in sync so agents on any platform have equivalent project knowledge.

### MCP Tools (all platforms)

| Tool | Description |
|---|---|
| `deploy_agentops_framework` | Deploy DAB to a workspace |
| `scaffold_agent_project` | Scaffold new agent from templates |
| `run_evaluation_suite` | Run eval, return metrics |
| `read_deployment_manifest` | Read `deployment_manifest.md` |
| `monitor_deployment` | Health check + optional live verification |
| `submit_trace_feedback` | Attach user/SME feedback to a production trace |
| `export_negative_traces` | Export negatively-rated traces for eval annotation |

### Claude Code

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentops": {
      "command": "python",
      "args": ["/path/to/agentops-redux/agentops_mcp/server.py"],
      "env": {
        "DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
        "DATABRICKS_TOKEN": "dapi...",
        "AGENTOPS_PROJECT_ROOT": "/path/to/agentops-redux"
      }
    }
  }
}
```

Project context is loaded automatically from `CLAUDE.md`. Skills documentation is in `skills/`.

### Cursor

MCP is pre-configured in `.cursor/mcp.json`. Open the project in Cursor and set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` as environment variables — the MCP server starts automatically.

Project rules are pre-configured in `.cursor/rules/agentops.mdc` and apply to all Python and YAML files in the project.

### Windsurf

MCP is pre-configured in `.windsurf/mcp.json`. Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` as environment variables.

Project context is loaded automatically from `.windsurfrules` at the project root.

### OpenAI Codex

Add to your Codex MCP configuration:

```json
{
  "mcpServers": {
    "agentops": {
      "command": "python",
      "args": ["agentops_mcp/server.py"],
      "env": {
        "DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
        "DATABRICKS_TOKEN": "dapi...",
        "AGENTOPS_PROJECT_ROOT": "."
      }
    }
  }
}
```

Project context is loaded automatically from `AGENTS.md`.

---

## Running Tests

```bash
# Unit tests (no Databricks required)
pytest tests/unit/ -v

# Integration tests (requires DATABRICKS_HOST + DATABRICKS_TOKEN)
AGENTOPS_ENV=staging pytest tests/integration/ -v

# Validation tests (full eval gate)
AGENTOPS_ENV=staging EVAL_SAMPLE_SIZE=5 pytest tests/validation/ -v
```

---

## Documentation

| Document | Description |
|---|---|
| [Intro + Quick Start](docs/intro.md) | Overview and first-run guide |
| [Architecture](docs/architecture.md) | Full multi-environment architecture reference |
| [Best Practices](docs/best-practices.md) | Observability, evaluation, and Human-in-the-Loop patterns |
| [Data Preparation](docs/data-preparation.md) | Ingestion, chunking, Vector Search indexing |
| [Agent Development](docs/agent-development.md) | Building agents with AgentBase and the router |
| [Evaluation](docs/evaluation.md) | Quality gates, scorers, and thresholds |
| [CI/CD](docs/ci-cd.md) | GitHub Actions pipeline setup |
| [Deployment](docs/deployment.md) | Deploying to Databricks with DAB |
| [Monitoring](docs/monitoring.md) | Production observability and online evaluation |
| [Extension Guide](docs/extension-guide.md) | Adding agents, data sources, and test types |
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnosis and fixes for common failure modes |

