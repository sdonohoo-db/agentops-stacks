<!--
title: AgentOps Redux — Troubleshooting Guide
description: Diagnostic guide for common failures in setup, deployment, evaluation, CI/CD, and MCP integration.
  Structured for both human engineers and AI coding agents.
tags: [troubleshooting, debugging, databricks, mlflow, evaluation, ci-cd, mcp]
-->

# Troubleshooting Guide

This guide covers the most common failure modes in AgentOps Redux, organized by component.
Each section follows a **Symptom → Cause → Fix** pattern so both humans and AI agents can quickly
locate and resolve issues without reading the entire document.

**For AI agents**: each section includes a `Diagnostic` command block you can run to confirm the root cause
before applying a fix.

---

## Table of Contents

1. [Installation & Setup](#1-installation--setup)
2. [Wheel Build Failures](#2-wheel-build-failures)
3. [Databricks Bundle Validation](#3-databricks-bundle-validation)
4. [Authentication & Permissions](#4-authentication--permissions)
5. [Unity Catalog Errors](#5-unity-catalog-errors)
6. [MLflow Errors](#6-mlflow-errors)
7. [Vector Search Errors](#7-vector-search-errors)
8. [Evaluation Gate Failures](#8-evaluation-gate-failures)
9. [Model Serving & Deployment](#9-model-serving--deployment)
10. [CI/CD Pipeline Issues](#10-cicd-pipeline-issues)
11. [MCP Server Issues](#11-mcp-server-issues)
12. [Batch Inferencing Issues](#12-batch-inferencing-issues)
13. [Multi-Cloud Node Type Issues](#13-multi-cloud-node-type-issues)
14. [Common Error Code Reference](#14-common-error-code-reference)

---

## 1. Installation & Setup

### 1.1 `ModuleNotFoundError: No module named 'mcp'`

**Symptom**: Starting `agentops_mcp/server.py` fails with an import error on `mcp`.

**Cause**: The `mcp[cli]` package is not installed.

**Fix**:
```bash
pip install "mcp[cli]>=1.0.0"
```

**Note**: If you see `No module named 'agentops_mcp'` instead, the local package is not installed.
Fix with:
```bash
pip install -e ".[mcp]"
```

---

### 1.2 `ModuleNotFoundError: No module named 'mlflow'` or `'databricks_langchain'`

**Symptom**: Any framework import fails at startup.

**Cause**: Dependencies not installed or the wrong virtual environment is active.

**Diagnostic**:
```bash
pip show mlflow databricks-langchain databricks-sdk
```

**Fix**:
```bash
pip install -e ".[dev]"
```

---

### 1.3 `DATABRICKS_HOST is not set` or `AgentOpsConfig` raises `ValueError`

**Symptom**: Framework initializes but immediately raises a `ValueError` about missing configuration.

**Cause**: Required environment variables are not exported.

**Diagnostic**:
```bash
echo $DATABRICKS_HOST
echo $DATABRICKS_TOKEN
echo $AGENTOPS_ENV
```

**Fix**: Export the required variables:
```bash
export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...
export AGENTOPS_ENV=dev
export AGENTOPS_DEV_CATALOG=agentops_dev
export AGENTOPS_PROD_CATALOG=agentops_prod
```

In Databricks jobs these are injected automatically via DAB variable substitution — only manual runs require explicit exports.

---

### 1.4 Python version compatibility errors

**Symptom**: Syntax errors, `TypeError` with type hints, or `from __future__ import annotations` warnings.

**Cause**: Python < 3.11 in use.

**Diagnostic**:
```bash
python --version
```

**Fix**: Use Python 3.11 or later. With pyenv:
```bash
pyenv install 3.11.8
pyenv local 3.11.8
```

---

### 1.5 Databricks CLI not configured

**Symptom**: `databricks bundle validate` or `deploy.py` fails with `Error: default profile not found`.

**Cause**: Databricks CLI has not been authenticated.

**Diagnostic**:
```bash
databricks auth describe
```

**Fix**:
```bash
databricks configure
# Enter: host (https://...), token (dapi...), cluster_id (optional)
```

Verify with:
```bash
databricks clusters list
```

---

## 2. Wheel Build Failures

### 2.1 `ERROR: No distributions found for agentops-framework`

**Symptom**: `databricks bundle deploy` fails with a missing wheel error in the job logs.

**Cause**: The Python wheel was never built before deploying. All DAB `python_wheel_task` entries depend on `dist/agentops_framework-*.whl`.

**Diagnostic**:
```bash
ls dist/agentops_framework-*.whl 2>/dev/null || echo "Wheel not built"
```

**Fix**:
```bash
pip install build
python -m build
```

Then re-run the deploy:
```bash
python scripts/deploy.py --target dev
```

`scripts/deploy.py` runs `python -m build` automatically before bundle deploy. If you are calling `databricks bundle deploy` directly, build the wheel first.

---

### 2.2 `pyproject.toml: No such file or directory`

**Symptom**: `python -m build` fails immediately.

**Cause**: Command was run from a subdirectory rather than the project root.

**Fix**: Always run build from the repository root:
```bash
cd /path/to/agentops-redux
python -m build
```

---

### 2.3 Entry point not found after wheel install

**Symptom**: DAB workflow fails with `EntryPointNotFound` or `command not found` for a console script.

**Cause**: A new entry point was added to `pyproject.toml [project.scripts]` but the wheel was not rebuilt.

**Fix**:
```bash
python -m build
# Then re-deploy
python scripts/deploy.py --target dev
```

---

## 3. Databricks Bundle Validation

### 3.1 `Error: variable 'node_type_standard' is not defined`

**Symptom**: `databricks bundle validate` fails with a variable resolution error.

**Cause**: A workflow YAML references `${var.node_type_standard}` but the variable is not declared in `databricks.yml`.

**Diagnostic**:
```bash
grep -n "node_type_standard" databricks.yml
```

**Fix**: Ensure `databricks.yml` declares all three node type variables:
```yaml
variables:
  node_type_standard:
    default: m5d.xlarge
  node_type_medium:
    default: m5d.2xlarge
  node_type_large:
    default: m5d.4xlarge
```

---

### 3.2 `Error: run_as: field 'service_principal_name' is invalid`

**Symptom**: Bundle validation or deploy fails because of an invalid `run_as` field.

**Cause**: The `run_as` block uses `service_principal_name` for a human user identity. Human users require `user_name`.

**Fix**: In `bundle/targets/prod.yml` and `bundle/targets/staging.yml`:
```yaml
run_as:
  user_name: ${workspace.current_user.userName}   # for human users
# OR
run_as:
  service_principal_name: my-sp@company.com       # for service principals
```

---

### 3.3 `Target 'prod' not found`

**Symptom**: `databricks bundle deploy --target prod` fails with a missing target error.

**Cause**: `databricks.yml` does not include the prod target file, or `bundle/targets/prod.yml` does not exist.

**Diagnostic**:
```bash
databricks bundle validate --target prod 2>&1 | head -20
ls bundle/targets/
```

**Fix**: Ensure `databricks.yml` includes all target files:
```yaml
include:
  - bundle/targets/dev.yml
  - bundle/targets/staging.yml
  - bundle/targets/prod.yml
```

---

### 3.4 `mode: development` in staging causes prod-unlike behavior

**Symptom**: Staging runs pass but issues appear immediately after prod deploy (permission errors, identity mismatches).

**Cause**: `bundle/targets/staging.yml` has `mode: development`, which skips identity enforcement and uses the deploying user's permissions rather than the `run_as` identity.

**Fix**: Set staging to production mode:
```yaml
targets:
  staging:
    mode: production
    run_as:
      user_name: ${workspace.current_user.userName}
```

---

## 4. Authentication & Permissions

### 4.1 `401 Unauthorized` from Databricks API

**Symptom**: Any SDK call or REST call returns HTTP 401.

**Cause**: `DATABRICKS_TOKEN` is expired, revoked, or incorrect.

**Diagnostic**:
```bash
curl -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "$DATABRICKS_HOST/api/2.0/clusters/list" | python -m json.tool | head -5
```

**Fix**: Generate a new token in the Databricks workspace UI under Settings > Developer > Access Tokens, then update the environment variable (or the secret in GitHub Actions).

---

### 4.2 `403 Forbidden` on Unity Catalog operations

**Symptom**: Catalog or schema creation, table reads/writes, or model registration fails with permission denied.

**Cause**: The identity running the job does not have sufficient Unity Catalog privileges.

**Diagnostic**:
```bash
databricks unity-catalog tables list --catalog agentops_dev --schema agentops 2>&1 | head -5
```

**Fix**: Grant the required privileges in Databricks:
```sql
-- In a Databricks SQL editor or notebook
GRANT USE CATALOG ON CATALOG agentops_dev TO `user@company.com`;
GRANT CREATE SCHEMA ON CATALOG agentops_dev TO `user@company.com`;
GRANT ALL PRIVILEGES ON SCHEMA agentops_dev.agentops TO `user@company.com`;
```

For service principals:
```sql
GRANT USE CATALOG ON CATALOG agentops_dev TO `service-principal://my-sp`;
```

---

### 4.3 GitHub Actions: `DATABRICKS_TOKEN is not set` in CI

**Symptom**: Integration or validation tests in GitHub Actions are skipped or fail with missing credential errors.

**Cause**: The `DATABRICKS_STAGING_HOST` or `DATABRICKS_STAGING_TOKEN` secrets are not set in the repository, or the job-level `if` condition uses `secrets.*` directly (which always evaluates false in GitHub Actions job-level expressions).

**Fix**:

1. Add the secrets in GitHub repository Settings > Secrets and variables > Actions.
2. Ensure the workflow sets env vars from secrets at workflow level:
```yaml
env:
  DATABRICKS_HOST: ${{ secrets.DATABRICKS_STAGING_HOST }}
  DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_STAGING_TOKEN }}
```
3. Reference `env.*` in job-level `if` conditions (not `secrets.*`):
```yaml
jobs:
  integration-tests:
    if: ${{ env.DATABRICKS_HOST != '' }}
```

---

## 5. Unity Catalog Errors

### 5.1 `Catalog 'agentops_dev' does not exist`

**Symptom**: Framework initialization or data preparation fails because the catalog is missing.

**Cause**: The Unity Catalog catalogs have not been created for the workspace.

**Fix**: Create the catalogs using Databricks CLI or SQL:
```bash
databricks unity-catalog catalogs create --name agentops_dev
databricks unity-catalog catalogs create --name agentops_prod
```

Or in SQL:
```sql
CREATE CATALOG IF NOT EXISTS agentops_dev;
CREATE CATALOG IF NOT EXISTS agentops_prod;
```

---

### 5.2 `Model version with alias '@champion' not found`

**Symptom**: Model Serving endpoint fails to start, or `load_model()` fails with alias not found.

**Cause**: The `@champion` alias has not been set on any model version yet. This happens when deploying for the first time before the App Deployment Workflow has completed.

**Fix**: Either run the full App Deployment Workflow, or set the alias manually for initial setup:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.registered_models.set_alias(
    full_name="agentops_dev.agentops.multi_agent_app",
    alias="champion",
    version_num=1,
)
```

**Warning**: Only set the alias manually for initial bootstrapping. In production, always let the deployment workflow set it after evaluation passes.

---

### 5.3 UC function registration fails with `ALREADY_EXISTS`

**Symptom**: `register_uc_function()` or tool registration raises a conflict error.

**Cause**: An older version of the function is already registered and the code uses `CREATE FUNCTION` instead of `CREATE OR REPLACE FUNCTION`.

**Fix**: The framework's `ToolRegistry.register()` uses `CREATE OR REPLACE FUNCTION` by default. If you see this error, check for direct SQL calls in custom tool registration code and replace `CREATE FUNCTION` with `CREATE OR REPLACE FUNCTION`.

---

## 6. MLflow Errors

### 6.1 `MlflowException: No active run`

**Symptom**: `mlflow.log_param()`, `mlflow.log_metric()`, or `mlflow.pyfunc.log_model()` fails with no active run.

**Cause**: These calls are made outside a `with mlflow.start_run():` context block.

**Fix**: Wrap model logging in a run context:
```python
import mlflow
set_experiment_for_env("my_agent", cfg)
with mlflow.start_run(run_name=f"my_agent_{cfg.env}"):
    agent.save(artifact_path="my_agent", registered_model_name=...)
```

For `mlflow.log_param()` calls in `AgentBase.__init__()` (which runs during Model Serving, where no active run exists), guard with:
```python
if mlflow.active_run():
    mlflow.log_param("agent_name", self.name)
```

---

### 6.2 `MlflowException: Experiment with name '/Users/...' does not exist`

**Symptom**: Evaluation or logging fails because the experiment path is not found.

**Cause**: The MLflow experiment does not exist yet in the target workspace.

**Fix**: The `set_experiment_for_env()` utility creates the experiment if it does not exist. If you are calling MLflow directly, use `mlflow.set_experiment()` with `create_if_not_exists=True`:
```python
mlflow.set_experiment("/Shared/agentops/rag_agent_staging")
```

Or use the framework utility:
```python
from framework.utils.mlflow_utils import set_experiment_for_env
set_experiment_for_env("rag_agent", cfg)
```

---

### 6.3 MLflow traces not appearing for LangChain calls

**Symptom**: Agent runs but no traces appear in the MLflow UI.

**Cause 1**: `mlflow.langchain.autolog()` was not called before the chain was constructed.
**Cause 2**: `mlflow.langchain.autolog()` is called inside `_invoke()` on every request, causing registration to fail silently after the first call.

**Fix**: Call autologging once in `__init__()`, before the chain is built:
```python
def __init__(self, ...):
    mlflow.langchain.autolog(log_traces=True, disable=False)
    self._chain = self._build_chain()   # autologging is now active
```

---

### 6.4 `MlflowException: Run not in ACTIVE state`

**Symptom**: Logging calls fail with a run state error.

**Cause**: A prior run was not properly closed (e.g., due to an exception during a previous run), leaving it in a non-terminal state.

**Fix**: End the stale run explicitly:
```python
import mlflow
if mlflow.active_run():
    mlflow.end_run()
```

Or search and close via the MLflow UI: go to the experiment, find the run marked "Running", and click End Run.

---

## 7. Vector Search Errors

### 7.1 `DatabricksError: Vector search endpoint 'agentops_vs_endpoint' not found`

**Symptom**: Data Preparation Workflow or RAG agent fails when trying to use Vector Search.

**Cause**: The Vector Search endpoint has not been created.

**Fix**: Create the endpoint via the Databricks SDK:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.vector_search_endpoints.create_endpoint(
    name="agentops_vs_endpoint",
    endpoint_type="STANDARD",
)
```

Or via the Databricks UI: Catalog > Vector Search > Create Endpoint.

Endpoint creation takes 5–15 minutes. Wait for status `ONLINE` before proceeding.

---

### 7.2 `Index not ready` or `Index status: PROVISIONING`

**Symptom**: Vector Search queries fail or return no results immediately after index creation.

**Cause**: The index is still being built. Delta Sync indexes require the initial sync to complete before they return results.

**Diagnostic**:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
index = w.vector_search_indexes.get_index(index_name="agentops_dev.agentops.knowledge_base_index")
print(index.status)
```

**Fix**: Wait for `status == "ONLINE"`. Initial sync typically takes 5–20 minutes depending on corpus size. Subsequent syncs after data updates are incremental and faster.

---

### 7.3 Vector Search returns empty results

**Symptom**: RAG agent returns generic responses with no retrieved context; `retrieved_context` is empty.

**Cause 1**: The index is online but the Delta table is empty (data preparation never ran or failed).
**Cause 2**: The embedding model name in the index does not match the one used at query time.
**Cause 3**: The query column names passed to `similarity_search()` do not match the index schema.

**Diagnostic**:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
# Check row count in the source Delta table
spark.table("agentops_dev.agentops.knowledge_base_chunks").count()
```

**Fix**:
- If the source table is empty, re-run the Data Preparation Workflow.
- If embeddings mismatch, verify `cfg.embedding_model` matches the index embedding config.
- If column names mismatch, check that `query_type` and column names in `VectorSearchRetriever` match the index schema.

---

### 7.4 `Embedding dimension mismatch`

**Symptom**: Index creation or query fails with a dimension error.

**Cause**: The embedding model was changed after the index was created, producing vectors of a different size.

**Fix**: Drop and recreate the index with the new embedding model:
```bash
# Delete the index via CLI or UI, then re-run Data Preparation Workflow
python scripts/deploy.py --target dev
```

---

## 8. Evaluation Gate Failures

### 8.1 Correctness score below threshold

**Symptom**: `EvaluationResult.passed()` returns False; correctness is below 0.80 (dev) or 0.90 (staging gate).

**Cause**: Agent responses are not matching expected answers in the eval dataset. Common reasons:
- Eval dataset expected responses are stale or don't match current agent behavior.
- Retrieved context is wrong (see Vector Search section).
- LLM endpoint was changed and the new model is less accurate.
- `scaffold_placeholder: true` entries were never updated.

**Diagnostic**: Check per-row eval results:
```python
result = evaluator.run(agent, "reference_agent/eval/eval_dataset.jsonl")
failed_rows = result.eval_table[result.eval_table["correctness/score"] < 0.8]
print(failed_rows[["request", "expected_response", "output", "correctness/score"]])
```

**Fix**:
1. Remove or update any entries with `"scaffold_placeholder": true` in metadata.
2. If expected responses are stale, update them to match current agent behavior.
3. If retrieval is poor, check Vector Search (section 7).
4. **Never lower the threshold to make the test pass** — fix the underlying quality issue.

---

### 8.2 Safety score below 1.0

**Symptom**: Evaluation fails specifically on the Safety metric; correctness and relevance may be fine.

**Cause**: One or more agent responses contain content the Safety judge flagged. Common triggers: unsafe instructions in context documents, overly detailed error messages, or jailbreak-style test questions in the eval dataset.

**Diagnostic**: Find which rows failed:
```python
unsafe_rows = result.eval_table[result.eval_table["safety/score"] < 1.0]
print(unsafe_rows[["request", "output", "safety/score"]])
```

**Fix**:
1. Review the flagged responses and the context documents that generated them.
2. Remove or sanitize unsafe content from source documents.
3. Enable AI Gateway guardrails in production to add a defense layer.
4. Do not remove the Safety threshold — it must be 1.0 at all stages.

---

### 8.3 `RetrievalGroundedness` score is low despite correct answers

**Symptom**: Agent gives correct answers but groundedness fails, suggesting the answer is not supported by retrieved context.

**Cause**: The agent is answering from LLM parametric memory rather than retrieved context, or the retrieved context is not included in the evaluation row.

**Fix**:
1. Ensure the eval dataset includes a `retrieved_context` column populated with the actual context used.
2. Verify the agent is using the retrieved context in its prompt — check the LangChain chain construction.
3. Increase `num_retrieved_chunks` if context is being cut off.

---

### 8.4 Eval fails because `eval_dataset.jsonl` has only placeholder entries

**Symptom**: Evaluation completes but correctness is near 0 for all rows; rows have `scaffold_placeholder: true` in metadata.

**Cause**: The eval dataset was generated by `scripts/scaffold.py` and the placeholder entries were never replaced with domain-specific questions and expected responses.

**Fix**:
1. Open the eval dataset file and replace entries where `scaffold_placeholder: true` with real questions and expected responses for your agent.
2. Aim for at least 15–20 entries covering the main use cases your agent is expected to handle.
3. Include a mix of easy (direct factual) and medium/hard (multi-step, ambiguous) questions.

---

### 8.5 `mlflow.genai.evaluate()` fails with schema errors

**Symptom**: Evaluation raises a `MlflowException` or `KeyError` about missing columns.

**Cause**: The eval dataset is missing required columns. `mlflow.genai.evaluate()` requires at minimum `request` and `expected_response` columns. `RetrievalGroundedness` additionally requires `retrieved_context`.

**Fix**: Verify dataset schema:
```python
import json, pandas as pd
rows = [json.loads(l) for l in open("reference_agent/eval/eval_dataset.jsonl")]
df = pd.DataFrame(rows)
print(df.columns.tolist())
# Must include: ['request', 'expected_response', 'retrieved_context']
```

---

## 9. Model Serving & Deployment

### 9.1 Endpoint creation fails with `RESOURCE_DOES_NOT_EXIST`

**Symptom**: App Deployment Workflow fails when creating the Model Serving endpoint.

**Cause**: The registered model referenced in the endpoint config does not exist in Unity Catalog (e.g., the Agent Development Workflow never ran successfully).

**Diagnostic**:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
models = list(w.registered_models.list(catalog_name="agentops_dev", schema_name="agentops"))
print([m.full_name for m in models])
```

**Fix**: Run the Agent Development Workflow first to register the model, then re-run App Deployment.

---

### 9.2 Endpoint is stuck in `UPDATING` state

**Symptom**: `monitor_deployment` or `verify.py` reports the endpoint is not `READY`, and the state has not changed for over 10 minutes.

**Cause**: The new model version is failing to load (import error, missing dependency, or wheel not uploaded).

**Fix**:
1. Check the endpoint event log in the Databricks UI (Model Serving > Endpoints > your-endpoint > Events).
2. Common cause: wheel was not rebuilt before deploy. Build and redeploy:
   ```bash
   python -m build
   python scripts/deploy.py --target dev
   ```
3. Check agent `__init__()` for initialization errors — these are surfaced in the event log.

---

### 9.3 Endpoint returns 500 errors on inference

**Symptom**: Test inference calls return HTTP 500 responses.

**Cause**: The agent is raising an unhandled exception during `_invoke()`.

**Fix**:
1. Check endpoint logs in the Databricks UI under Model Serving > Logs.
2. Test locally with a mock context:
   ```python
   agent = RAGAgent(config=cfg)
   result = agent.predict(None, {"messages": [{"role": "user", "content": "test"}]})
   ```
3. Common causes: Vector Search index not ready, Unity Catalog permissions, missing environment variables.

---

### 9.4 Canary deployment not receiving traffic

**Symptom**: `enable_canary=True` was set but all traffic still goes to the champion model.

**Cause**: The endpoint does not support traffic splitting (requires `PROVISIONED_THROUGHPUT` workload type) or the canary version was not registered before calling `deploy()`.

**Fix**: Ensure the model version is registered before initiating canary. Canary traffic splitting requires the endpoint to be configured with `PROVISIONED_THROUGHPUT`. For `SERVERLESS` endpoints, traffic splitting is not supported — use blue/green deployment instead (deploy a new endpoint and shift DNS/routing).

---

## 10. CI/CD Pipeline Issues

### 10.1 Integration tests are always skipped in GitHub Actions

**Symptom**: The `integration-tests` job shows as skipped even though Databricks secrets are configured.

**Cause**: The job-level `if` condition references `secrets.*` directly, which GitHub Actions always evaluates as empty at the job level (secrets are masked in expressions).

**Fix**: Set env vars from secrets at the workflow level and reference `env.*` in job conditions:
```yaml
# At workflow level:
env:
  DATABRICKS_HOST: ${{ secrets.DATABRICKS_STAGING_HOST }}

# At job level:
jobs:
  integration-tests:
    if: ${{ env.DATABRICKS_HOST != '' }}   # Works
    # NOT: if: ${{ secrets.DATABRICKS_STAGING_HOST != '' }}   # Always false
```

---

### 10.2 CI fails on `databricks bundle validate` with wheel not found

**Symptom**: Bundle validation step fails because the wheel artifact is referenced but does not exist in the workspace.

**Cause**: The CI workflow is running `databricks bundle validate` before building the wheel.

**Fix**: Add the build step before validation in `.github/workflows/ci.yml`:
```yaml
- name: Build wheel
  run: |
    pip install build
    python -m build

- name: Validate bundle
  run: databricks bundle validate --target staging
```

---

### 10.3 CD pipeline deploys to prod without staging approval

**Symptom**: A merge to `release` triggers the prod CD workflow and deploys immediately with no gate.

**Cause**: The `production-deploy` job in `cd.yml` is not gated behind a manual approval environment.

**Fix**: Add a GitHub environment with required reviewers to the prod deploy job:
```yaml
jobs:
  production-deploy:
    environment: production   # Configure this env in GitHub with required reviewers
    steps:
      ...
```

Configure the `production` environment in repository Settings > Environments > New environment > Required reviewers.

---

### 10.4 Validation tests time out in CI

**Symptom**: The `validation-tests` GitHub Actions job exceeds the timeout and is cancelled.

**Cause**: MLflow GenAI evaluation calls the LLM for each eval row. A large eval dataset (75 rows) with slow judge models can take 15–30 minutes.

**Fix**:
1. Use `--sample` for CI validation to limit eval rows:
   ```yaml
   - name: Validation tests
     run: EVAL_SAMPLE_SIZE=20 pytest tests/validation/ -v
   ```
2. The full eval (all 75 rows) should run in the nightly monitoring workflow, not on every PR.

---

## 11. MCP Server Issues

### 11.1 MCP server fails to start with `ImportError: cannot import name 'FastMCP' from 'mcp'`

**Symptom**: Starting `agentops_mcp/server.py` fails with an import error.

**Cause**: The installed `mcp` package is an older version that does not include `FastMCP`.

**Fix**:
```bash
pip install "mcp[cli]>=1.0.0" --upgrade
```

---

### 11.2 Claude Code / Cursor / Windsurf cannot find the MCP server

**Symptom**: The AI coding platform reports that the `agentops` MCP server failed to start or is not connected.

**Cause 1**: The `AGENTOPS_PROJECT_ROOT` environment variable is not set, so the server cannot locate project files.
**Cause 2**: The path to `server.py` in the MCP config is wrong.
**Cause 3**: Python virtual environment with `mcp[cli]` is not the one being invoked.

**Diagnostic**: Run the server manually and check for errors:
```bash
python agentops_mcp/server.py
```

**Fix**:
- For Claude Code: update `~/.claude/claude_desktop_config.json` with the correct absolute path.
- For Cursor: verify `.cursor/mcp.json` references `${workspaceFolder}` — ensure you opened the project root as the workspace folder.
- For Windsurf: verify `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are exported in your shell profile.
- To use a specific Python: replace `"command": "python"` with the full path, e.g., `"/Users/you/.venv/bin/python"`.

---

### 11.3 MCP tool calls return errors about missing `DATABRICKS_HOST`

**Symptom**: MCP tools start but every tool call fails with a configuration error.

**Cause**: Environment variables are not being passed to the MCP server process.

**Fix**: Add the env vars to the MCP server configuration:
```json
{
  "mcpServers": {
    "agentops": {
      "command": "python",
      "args": ["/path/to/agentops_mcp/server.py"],
      "env": {
        "DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
        "DATABRICKS_TOKEN": "dapi...",
        "AGENTOPS_PROJECT_ROOT": "/path/to/agentops-redux",
        "AGENTOPS_ENV": "dev"
      }
    }
  }
}
```

---

### 11.4 MCP server shadows the installed `mcp` package (namespace collision)

**Symptom**: `from mcp.server.fastmcp import FastMCP` fails with `ImportError` even though `mcp[cli]` is installed. Error mentions a local `mcp/` directory.

**Cause**: The local directory named `mcp/` at the project root is being picked up before the installed `mcp` package because the project root is inserted at the front of `sys.path`.

**Fix**: The correct directory name is `agentops_mcp/` (not `mcp/`). If you have a local `mcp/` directory, rename it:
```bash
mv mcp/ agentops_mcp/
# Then update any imports from 'mcp.tools.*' to 'agentops_mcp.tools.*'
```

The server uses `sys.path.append()` (not `insert(0, ...)`) to avoid this collision.

---

## 12. Batch Inferencing Issues

### 12.1 Batch job fails with HTTP 429 from the Model Serving endpoint

**Symptom**: Batch Inferencing Workflow fails mid-run with rate limit errors.

**Cause**: The Spark UDF is making too many concurrent requests and exceeding the `rate_limit_per_minute` configured on the AI Gateway.

**Fix**: Reduce Spark parallelism or add inter-batch delays. In the batch inferencer config:
```python
inferencer = BatchInferencer(
    endpoint_name=cfg.serving_endpoint_name,
    requests_per_second=1.5,    # Reduce from default
    batch_size=10,              # Smaller batches
)
```

Alternatively, temporarily raise `rate_limit_per_minute` in `bundle/targets/prod.yml` for the duration of the batch run, then restore it.

---

### 12.2 Batch output table has null values in the response column

**Symptom**: Batch run completes without errors but many output rows have `null` in the response column.

**Cause**: Individual inference calls are failing silently. The batch inferencer catches per-row exceptions and writes `null` rather than failing the entire job.

**Diagnostic**: Check the `error` column in the output Delta table:
```sql
SELECT input, error, COUNT(*) as cnt
FROM agentops_prod.agentops.batch_inference_output
WHERE response IS NULL
GROUP BY input, error
ORDER BY cnt DESC
LIMIT 20;
```

**Fix**: Address the errors surfaced in the `error` column. Common causes: malformed input, endpoint authentication errors, or individual inputs that trigger safety filters.

---

## 13. Multi-Cloud Node Type Issues

### 13.1 `Instance type 'm5d.xlarge' is not available in this region`

**Symptom**: DAB job cluster creation fails because the default AWS instance type is not available.

**Cause**: The workspace is on Azure or GCP, but the default node type variables still reference AWS instance types.

**Fix**: Override node type variables at deploy time:

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

To make overrides permanent, set default values in the appropriate target file:
```yaml
# bundle/targets/dev.yml
variables:
  node_type_standard: Standard_DS3_v2
  node_type_medium: Standard_DS4_v2
  node_type_large: Standard_DS5_v2
```

See [docs/deployment.md](docs/deployment.md) → "Multi-Cloud Cluster Configuration" for a full comparison table.

---

### 13.2 Cluster creation fails with `INSTANCE_TYPE_NOT_SUPPORTED`

**Symptom**: Job cluster creation fails immediately with an unsupported instance type error.

**Cause**: Instance type chosen does not support the cluster features required (e.g., GPU, local NVMe, or specific runtime).

**Fix**: Verify the instance type is available in your workspace region using the Databricks UI under Compute > Create Cluster > Node Type. Choose an instance type from the same family with the required specs.

---

## 14. Common Error Code Reference

Quick-reference for error codes that appear frequently in logs.

| Code | Where | Meaning | Typical Fix |
|---|---|---|---|
| `401 Unauthorized` | Databricks API / Model Serving | Token expired or invalid | Rotate `DATABRICKS_TOKEN` |
| `403 Forbidden` | Unity Catalog / Model Serving | Missing permissions | Grant UC privileges or fix `run_as` identity |
| `404 Not Found` | Model Serving / MLflow | Endpoint or experiment does not exist | Run App Deployment Workflow; create experiment |
| `429 Too Many Requests` | Model Serving API | Rate limit exceeded | Reduce request rate; raise `rate_limit_per_minute` |
| `500 Internal Server Error` | Model Serving | Agent raised an exception during inference | Check endpoint event log; debug `_invoke()` locally |
| `RESOURCE_DOES_NOT_EXIST` | Databricks SDK | Referenced asset (model, endpoint, catalog) not found | Verify DAB workflows ran in correct order |
| `INVALID_STATE` | Databricks SDK | Operation not valid for current resource state | Wait for pending operation to complete |
| `EntryPointNotFound` | DAB `python_wheel_task` | Console script not in installed wheel | Rebuild wheel: `python -m build` |
| `MlflowException: No active run` | MLflow | Logging called outside `start_run` context | Wrap with `with mlflow.start_run():` |
| `DatabricksError: Index not ready` | Vector Search | Index still provisioning | Wait for `status == ONLINE`; takes 5–20 min |
| `scaffold_placeholder: true` | Eval dataset | Eval entries were never replaced post-scaffold | Update eval dataset with real domain questions |

---

## Getting More Help

- **MLflow docs**: https://mlflow.org/docs/latest/llms/llm-evaluate/
- **Databricks Asset Bundles docs**: https://docs.databricks.com/en/dev-tools/bundles/
- **Databricks Vector Search docs**: https://docs.databricks.com/en/generative-ai/vector-search.html
- **Model Serving docs**: https://docs.databricks.com/en/machine-learning/model-serving/
- **Unity Catalog privileges reference**: https://docs.databricks.com/en/data-governance/unity-catalog/manage-privileges/

For deployment state questions, always read `deployment_manifest.md` first — it is the authoritative record of what is currently deployed.
For evaluation failures, always check the MLflow experiment UI for per-row trace details before editing code.
