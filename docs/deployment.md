---
title: Deployment
description: Package agents with MLflow, register in Unity Catalog, and deploy Model Serving endpoints via Databricks Asset Bundles
category: deployment
tags: [deployment, mlflow, model-serving, unity-catalog, champion-alias, asset-bundles]
related_docs: [agent-development.md, evaluation.md, ci-cd.md, monitoring.md]
---

# Deployment

Deployment packages agents as MLflow models, registers them in Unity Catalog, sets the `@champion` alias, and creates or updates a Model Serving endpoint. All of this is orchestrated by the app deployment DAB workflow.

---

## Deployment Flow

```
AgentDeployer.deploy(agent)
    ↓
mlflow.pyfunc.log_model()       — Log to MLflow experiment
    ↓
mlflow.register_model()         — Register in Unity Catalog
    ↓
client.set_registered_model_alias("champion", version)
    ↓
AppDeployer.deploy(model_name)  — Create/update Model Serving endpoint
    ↓
Wait for endpoint state = READY
    ↓
generate_manifest.py            — Write deployment_manifest.md
```

---

## App Deployment Workflow (DAB)

**File:** `bundle/resources/app_deployment_workflow.yml`

Three tasks run in sequence:

```
agent1_deploy → agent2_deploy → app_deploy
```

Each `*_deploy` task calls a Python script that:
1. Instantiates the agent
2. Calls `AgentDeployer.deploy()` to log + register the model
3. Sets the `@champion` alias

The final `app_deploy` task calls `AppDeployer.deploy()` to create or update the endpoint.

### Prerequisite: Build the Wheel

All DAB workflow tasks use `python_wheel_task`, which requires a built wheel in `dist/`. Build it before deploying:

```bash
pip install build
python -m build    # creates dist/agentops_framework-*.whl
```

`scripts/deploy.py` runs this automatically. If invoking `databricks bundle deploy` directly, build the wheel first.

### Triggering

```bash
# Via scripts (builds wheel automatically)
python scripts/deploy.py --target dev

# Via DAB directly (build wheel first)
python -m build
databricks bundle deploy --target dev
databricks jobs run-now --job-id <app_deployment_job_id>
```

---

## Agent Deployment (`AgentDeployer`)

`framework/deployment/deploy_agent.py`

```python
from framework.deployment.deploy_agent import AgentDeployer
from reference_agent.agents.agent1.agent import RAGAgent

deployer = AgentDeployer(agent_name="rag_agent")
result = deployer.deploy(
    agent=RAGAgent(),
    pip_requirements=[
        "mlflow>=2.17.0",
        "databricks-sdk>=0.30.0",
        "databricks-langchain>=0.3.0",
        "langchain>=0.3.0",
    ],
)

if result.success:
    print(f"Deployed: {result.model_uri}")
    # models:/agentops_dev.agentops.rag_agent@champion
else:
    print(f"Failed: {result.errors}")
```

### What `deploy()` does

1. Opens an MLflow run with name `{agent_name}_deploy_{env}`
2. Calls `mlflow.pyfunc.log_model()` with the agent as a `PythonModel`
3. Registers the model in UC as `{active_catalog_schema}.{agent_name}`
4. Sets `@champion` alias on the new version
5. Returns `DeploymentResult` with the model URI

### The `@champion` alias

The serving endpoint always points to `models:/{model_name}@champion`. When you deploy a new version:

1. New version is registered (e.g., version 7)
2. `@champion` alias is moved from version 6 → version 7
3. Endpoint config is updated to serve version 7
4. No endpoint config change needed if you want gradual rollout — just move the alias

For **A/B testing** (challenger deployment):

```python
result = deployer.deploy(
    agent=new_agent_version,
    alias="challenger",
)
# Endpoint now serves @champion (80%) and @challenger (20%)
# via traffic split in serving endpoint config
```

---

## Endpoint Deployment (`AppDeployer`)

`framework/deployment/deploy_app.py`

```python
from framework.deployment.deploy_app import AppDeployer

deployer = AppDeployer()  # Uses config.model_serving_endpoint
result = deployer.deploy(
    model_name="agentops_dev.agentops.multi_agent_app",
    model_alias="champion",
    scale_to_zero=True,     # dev: OK to scale to zero
    workload_size="Small",  # dev: small workload
)

print(f"Endpoint: {result.endpoint_url}")
print(f"State: {result.state}")  # READY
```

### Prod settings

```python
result = deployer.deploy(
    model_name="agentops_prod.agentops.multi_agent_app",
    model_alias="champion",
    scale_to_zero=False,    # prod: no cold starts
    workload_size="Medium", # prod: larger workload
    timeout_seconds=900,
)
```

### Test inference

After deployment, verify the endpoint responds:

```python
response = deployer.invoke({
    "messages": [{"role": "user", "content": "What is the refund policy?"}]
})
print(response)
# {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
```

---

## The Top-Level App (`reference_agent/app.py`)

`MultiAgentApp` is the deployable wrapper around the router. It's what gets logged to MLflow and served.

```python
from reference_agent.app import MultiAgentApp

app = MultiAgentApp()
app.deploy()  # Logs, registers, and sets @champion
```

Or deploy it directly from the script:

```bash
python -c "from reference_agent.app import MultiAgentApp; MultiAgentApp().deploy()"
```

The `MultiAgentApp.predict()` signature follows the standard MLflow serving format:

```python
# Request format (OpenAI Chat compatible)
{
    "messages": [
        {"role": "user", "content": "What is the vacation policy?"}
    ]
}

# Response format
{"role": "assistant", "content": "The vacation policy is..."}
```

---

## Deployment Manifest

After every deployment, `scripts/generate_manifest.py` writes `deployment_manifest.md`:

```bash
python scripts/generate_manifest.py --target prod
```

The manifest contains:
- Deployment timestamp and target environment
- Workspace URL
- Per-workflow: job ID, URL, last run status
- Unity Catalog: catalog, schema, model names, vector index names, function names
- Model Serving endpoint: URL, state, model version
- MLflow experiments: IDs and URLs

Example:

```markdown
---
deployment_status: SUCCESS
environment: prod
timestamp: 2026-03-20T14:32:00Z
workspace: https://prod.azuredatabricks.net
---

## Workflows
| Workflow | Job ID | Last Run |
|---|---|---|
| data_preparation | 12345 | SUCCESS |
| agent_development | 12346 | SUCCESS |
| app_deployment | 12347 | SUCCESS |

## Model Serving
- Endpoint: agentops-prod-endpoint
- URL: https://prod.azuredatabricks.net/serving-endpoints/agentops-prod-endpoint/invocations
- State: READY
- Model: agentops_prod.agentops.multi_agent_app@champion (version 3)
```

---

## Verification

After deployment, run `scripts/verify.py` to confirm everything is live:

```bash
python scripts/verify.py --target prod --test-inference
```

This:
1. Reads `deployment_manifest.md`
2. Makes HTTP calls to each listed job URL, endpoint URL, and UC model
3. Sends a test inference to the endpoint
4. Writes `verification_report.md` with pass/fail per component
5. Exits 0 (all pass) or 1 (any failure)

---

## Rollback

To roll back to a previous version:

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Move @champion back to version 5
client.set_registered_model_alias(
    name="agentops_prod.agentops.multi_agent_app",
    alias="champion",
    version="5",
)

# Update endpoint to serve the new champion
from framework.deployment.deploy_app import AppDeployer
deployer = AppDeployer()
deployer.deploy(model_name="agentops_prod.agentops.multi_agent_app")
```

---

## Environment-Specific Endpoint Names

Endpoint names are configured in the DAB bundle variables:

| Environment | Endpoint Name |
|---|---|
| dev | `agentops-dev-endpoint` |
| staging | `agentops-staging-endpoint` |
| prod | `agentops-prod-endpoint` |

Overridden in `bundle/targets/{env}.yml`:

```yaml
variables:
  model_serving_endpoint: agentops-prod-endpoint
  serving_workload_size: Medium
  serving_scale_to_zero: "false"
```

## Multi-Cloud Cluster Configuration

Job cluster node types default to AWS instance families. Override `node_type_standard`, `node_type_medium`, and `node_type_large` in your target config or at deploy time for Azure or GCP.

| Variable | Purpose | AWS default | Azure equivalent | GCP equivalent |
|---|---|---|---|---|
| `node_type_standard` | Agent dev, app deploy, monitoring | `m5d.xlarge` | `Standard_DS3_v2` | `n1-standard-4` |
| `node_type_medium` | Data preparation | `m5d.2xlarge` | `Standard_DS4_v2` | `n1-standard-8` |
| `node_type_large` | Batch inferencing | `m5d.4xlarge` | `Standard_DS5_v2` | `n1-standard-16` |

Override example for Azure in `bundle/targets/dev.yml`:

```yaml
variables:
  node_type_standard: Standard_DS3_v2
  node_type_medium: Standard_DS4_v2
  node_type_large: Standard_DS5_v2
```

Or override at deploy time:

```bash
databricks bundle deploy --target dev \
  --var="node_type_standard=Standard_DS3_v2" \
  --var="node_type_medium=Standard_DS4_v2" \
  --var="node_type_large=Standard_DS5_v2"
```
