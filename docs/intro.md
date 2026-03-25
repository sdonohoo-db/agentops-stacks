---
title: AgentOps Redux — Overview & Quick Start
description: Introduction to the AgentOps framework for developing, evaluating, and promoting AI agents on Databricks
category: getting-started
tags: [overview, quick-start, architecture, databricks, agents]
related_docs: [architecture.md, agent-development.md, ci-cd.md, deployment.md]
---

# AgentOps Redux — Overview & Quick Start

AgentOps Redux is an opinionated, production-ready framework for building, evaluating, and deploying AI agents on Databricks. It provides the scaffolding, patterns, and automation needed to take agents from a notebook experiment to a governed, monitored production system.

## What it Solves

| Problem | AgentOps Solution |
|---|---|
| Ad-hoc agent code with no structure | `AgentBase` enforces MLflow-compatible interface |
| Evaluation skipped before promotion | Quality gates block deployment until thresholds pass |
| No traceability across environments | MLflow tracing on every agent call, in every env |
| Manual multi-environment deployment | Databricks Asset Bundles + GitHub Actions CI/CD |
| Hard to add new agents | `scaffold.py` + router auto-registration |

---

## Repository Layout

```
agentops-redux/
├── framework/          # Reusable Python library (AgentBase, Router, Evaluator, etc.)
├── reference_agent/    # Complete working RAG agent demonstrating every framework layer
├── bundle/             # Databricks Asset Bundle (dev/staging/prod targets)
├── tests/              # Unit → integration → validation test tiers
├── scripts/            # CLI: deploy, scaffold, verify, manifest
├── skills/             # Claude Code plugin skills (/deploy-agentops, /scaffold-agent, etc.)
├── mcp/                # FastMCP server (same 5 operations as tools)
└── docs/               # This directory
```

---

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Set environment variables

```bash
export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...
export AGENTOPS_ENV=dev
export AGENTOPS_DEV_CATALOG=agentops_dev
export AGENTOPS_PROD_CATALOG=agentops_prod
```

### 3. Run unit tests

```bash
pytest tests/unit/ -v
```

### 4. Try the reference agent locally

```python
from reference_agent.router.router import build_router

router = build_router()
result = router.predict(None, {
    "messages": [{"role": "user", "content": "What is the AgentOps framework?"}]
})
print(result)
```

### 5. Deploy to dev workspace

```bash
python scripts/deploy.py --target dev
```

This validates the bundle, deploys all workflows, generates `deployment_manifest.md`, and runs verification.

---

## Environment Model

AgentOps follows a **branch = environment** model:

| Branch | Environment | Catalog | Triggered By |
|---|---|---|---|
| `dev` | dev | `agentops_dev` | Push to `dev` |
| `main` | staging | `agentops_dev` | PR merge to `main` |
| `release` | prod | `agentops_prod` | Push to `release` |

The dev catalog has **read-only access** to the prod catalog. Agents are never trained or fine-tuned on prod data directly — they read from it via governed Delta tables and Vector Search indexes.

---

## The Promotion Gate

An agent cannot be promoted to the next environment without passing evaluation thresholds:

```
correctness   >= 0.80
groundedness  >= 0.90
relevance     >= 0.80
safety        >= 1.00
```

These are enforced by `EvaluationThresholds` in `framework/evaluation/evaluator.py` and checked in CI before `databricks bundle deploy` runs.

---

## Key Concepts

### AgentBase
Every agent extends `AgentBase(mlflow.pyfunc.PythonModel)`. Subclasses implement `_invoke()`. The base class handles MLflow tracing, UC model registration, and the standard `predict()` interface.

### AgentRouter
Single entry point for multi-agent applications. Routes incoming messages to registered agents using keyword matching (fast path) or LLM intent classification (fallback). Add new agents by calling `router.register_agent()`.

### MLflow Tracing
`@mlflow.trace` is applied to every `predict()` call. Every agent invocation produces a trace viewable in the MLflow UI. Traces are the primary observability signal for production monitoring.

### Unity Catalog
All model artifacts, eval datasets, and tools are registered in Unity Catalog. The `@champion` alias always points to the currently serving model version.

### Databricks Asset Bundles (DAB)
All infrastructure is declared as code in `bundle/`. Each environment has its own `targets/` YAML with workspace-specific overrides. Deploy with `databricks bundle deploy --target <env>`.

---

## Installing Claude Code Skills

```bash
# From the project root:
claude mcp install skills/skill_manifest.json
```

Available skills:
- `/deploy-agentops` — Deploy to a target environment
- `/scaffold-agent` — Create a new agent from templates
- `/run-eval` — Run evaluation suite and surface results
- `/read-manifest` — Read and interpret the deployment manifest
- `/monitor-deployment` — Check endpoint health and trace quality

## Installing the MCP Server

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

---

## Next Steps

- [Architecture](architecture.md) — Detailed architecture reference
- [Agent Development](agent-development.md) — Build and register agents
- [Evaluation](evaluation.md) — Configure quality gates
- [Data Preparation](data-preparation.md) — Ingest and index documents
- [CI/CD](ci-cd.md) — GitHub Actions pipeline configuration
- [Deployment](deployment.md) — Bundle deploy and model serving
- [Monitoring](monitoring.md) — MLflow traces, metrics, alerts
- [Extension Guide](extension-guide.md) — Add Agent 3+, new data sources
