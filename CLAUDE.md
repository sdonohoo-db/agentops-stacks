# AgentOps Redux — AI Agent Instructions

> This file tells AI coding agents (Claude Code, Cursor, etc.) how to work with this repository effectively.

## What This Repo Is

AgentOps Redux is a production-ready framework for developing, evaluating, and promoting AI agents on Databricks. It follows the architecture in `agentops_architecture_decomposition.md`.

**Do not confuse this with a demo or tutorial.** This is a deployable framework. Changes here affect real Databricks workspaces.

## Project Layout (Critical Files)

```
framework/config.py           ← Single source of config (AgentOpsConfig). Read this first.
framework/agent_development/  ← AgentBase, Router, ToolRegistry — start here for agent work
framework/evaluation/         ← MLflow GenAI evaluation wrappers
databricks.yml                ← DAB root config — environment variables defined here
reference_agent/app.py        ← Top-level mlflow.pyfunc model (what gets deployed)
reference_agent/router/       ← Multi-agent router (routes to agent1 or agent2)
scripts/deploy.py             ← Deploy to Databricks workspace
scripts/verify.py             ← Verify deployment + write verification_report.md
deployment_manifest.md        ← GENERATED — shows what's deployed (read before ops tasks)
```

## Environment Setup

All configuration comes from environment variables (set by DAB or manually):

```bash
export AGENTOPS_ENV=dev                          # dev | staging | prod
export DATABRICKS_HOST=https://your.workspace.com
export DATABRICKS_TOKEN=dapi...
export AGENTOPS_DEV_CATALOG=agentops_dev
export AGENTOPS_PROD_CATALOG=agentops_prod
```

In Databricks jobs, these are injected by bundle variable substitution.

## Common Tasks

### Add a new agent
```bash
python scripts/scaffold.py --name <name> --description "<desc>" --type rag
```
Then implement `_invoke()` in `reference_agent/agents/<name>/agent.py`.
Register in `reference_agent/router/router.py`.

### Run evaluation
```bash
python reference_agent/eval/run_eval.py --sample 5  # quick dev check
python reference_agent/eval/run_eval.py             # full eval
```

### First-time workspace setup (run once per workspace)
```bash
cp .env.example .env                     # fill in DATABRICKS_HOST, DATABRICKS_TOKEN, AGENTOPS_ENV
python scripts/setup.py                  # creates catalogs, schemas, VS endpoint, MLflow experiments
```

### Deploy
```bash
pip install build && python -m build     # build wheel first (required by DAB workflows)
python scripts/deploy.py --target dev
databricks bundle validate --target dev  # validate only
```

### Verify deployment
```bash
python scripts/verify.py --target dev --test-inference
```

### Run unit tests
```bash
pytest tests/unit/ -v
```

## Key Interfaces

### AgentBase (all agents inherit this)

```python
from framework.agent_development.agent_base import AgentBase

class MyAgent(AgentBase):
    def __init__(self):
        super().__init__(name="my_agent", description="Does X")

    def _invoke(self, messages, context=None) -> str:
        # Your logic here
        return "response"
```

### AgentOpsConfig (single source of truth)

```python
from framework.config import get_config
cfg = get_config()
print(cfg.active_catalog_schema)  # agentops_dev.agentops
print(cfg.llm_endpoint)           # databricks-meta-llama-3-3-70b-instruct
```

### Evaluation

```python
from framework.evaluation.evaluator import AgentEvaluator
evaluator = AgentEvaluator(agent_name="my_agent")
result = evaluator.run(agent=my_agent, eval_data="path/to/eval.jsonl")
assert result.passed()
```

## Deployment Architecture (Do Not Bypass)

The deployment flow is: **dev branch → staging CI → main → release → prod CD**

- Never write directly to Prod Catalog from dev code
- Never skip evaluation gates before promoting
- Always run `verify.py` after deployment and check `deployment_manifest.md`
- The `@champion` alias on UC models is what prod serving targets — set it only after eval passes

## Testing Standards

- **Unit tests** (`tests/unit/`): Pure Python, no Databricks. Run without env vars.
- **Integration tests** (`tests/integration/`): Require `DATABRICKS_HOST`. Test real catalog/MLflow.
- **Validation tests** (`tests/validation/`): Require full Dev Catalog. Run in staging CI only.

## Multi-Cloud Node Types

Job clusters default to AWS (`m5d.xlarge/2xlarge/4xlarge`). Override via bundle variables for other clouds:

```bash
# Azure
databricks bundle deploy --target dev \
  --var="node_type_standard=Standard_DS3_v2" \
  --var="node_type_medium=Standard_DS4_v2" \
  --var="node_type_large=Standard_DS5_v2"

# GCP
databricks bundle deploy --target dev \
  --var="node_type_standard=n1-standard-4" \
  --var="node_type_medium=n1-standard-8" \
  --var="node_type_large=n1-standard-16"
```

See `docs/deployment.md` → "Multi-Cloud Cluster Configuration" for full table.

## Dependencies & Versions

Key packages (always use these versions or newer):
```
mlflow>=2.17.0
databricks-sdk>=0.30.0
databricks-langchain>=0.3.0
langchain>=0.3.0
mcp[cli]>=1.0.0  # for MCP server only
```

## Troubleshooting

If a deployment, evaluation, or tool call fails, consult `TROUBLESHOOTING.md` before attempting fixes.
It is structured as Symptom → Cause → Fix and covers:
- Wheel build failures (section 2)
- Bundle validation errors (section 3)
- MLflow `No active run` and trace issues (section 6)
- Vector Search not ready / empty results (section 7)
- Evaluation gate failures and placeholder entries (section 8)
- Model Serving 500 errors and stuck endpoints (section 9)
- MCP server namespace collision (section 11)

Always read `deployment_manifest.md` before any operational task to understand what is currently deployed.

## What NOT To Do

- Do not hardcode workspace URLs or tokens in code — use env vars
- Do not write to Prod Catalog directly from dev or staging code
- Do not skip evaluation thresholds by lowering them to pass failing tests
- Do not modify `deployment_manifest.md` by hand — it is auto-generated
- Do not run `scripts/deploy.py --target prod` without running `--target staging` first
- Do not add new dependencies to `framework/` without updating `pyproject.toml`
