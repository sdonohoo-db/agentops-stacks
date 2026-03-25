---
name: monitor-deployment
description: Monitor a running AgentOps deployment for health and quality issues
trigger: /monitor-deployment
category: operations
tags: [agentops, monitoring, health, mlflow, serving]
---

Monitor a running AgentOps deployment by checking endpoint health, trace volumes, and quality metrics.

## When to use
Use this skill when the user wants to:
- Check if the production endpoint is healthy
- Review recent MLflow trace quality metrics
- Detect anomalies or regressions in production
- Get a health summary of the current deployment

## What you should do

1. **Read the current deployment state** from `deployment_manifest.md`

2. **Check endpoint health**:
   ```python
   from framework.deployment.deploy_app import AppDeployer
   deployer = AppDeployer()
   # Check endpoint state via Databricks SDK
   from databricks.sdk import WorkspaceClient
   client = WorkspaceClient()
   endpoint = client.serving_endpoints.get(name="agentops_endpoint")
   print(endpoint.state)
   ```

3. **Check recent MLflow traces** (last 24 hours):
   ```python
   import mlflow
   from mlflow.tracking import MlflowClient
   client = MlflowClient()
   # Search for recent production runs
   runs = client.search_runs(
       experiment_ids=["<prod_experiment_id>"],
       filter_string="attribute.start_time > 1000000000000",  # adjust timestamp
       order_by=["attribute.start_time DESC"],
       max_results=50,
   )
   ```

4. **Check for quality regressions** by comparing recent eval metrics to baseline:
   - If correctness dropped > 5% from baseline: flag as regression
   - If error rate increased: investigate endpoint logs
   - If trace volume dropped to zero: check if endpoint is receiving traffic

5. **Report findings**:
   | Metric | Status | Value |
   |---|---|---|
   | Endpoint State | 🟢/🔴 | READY / NOT_READY |
   | Recent Traces (24h) | 🟢/🟡 | count |
   | Avg Correctness | 🟢/🔴 | score |
   | Error Rate | 🟢/🔴 | percentage |

6. **Recommend actions** if issues found:
   - Endpoint down: `databricks bundle deploy --target prod`
   - Quality regression: trigger re-evaluation and consider rollback
   - No traffic: check routing and application connectivity

## Key monitoring signals
- **Endpoint state**: Must be READY
- **Error rate**: Should be < 1% of requests
- **Trace latency (p95)**: Establish baseline in dev; alert if 2x in prod
- **Correctness score**: Should not drop > 5% from staging baseline
- **Groundedness score**: Critical for RAG agents — drops indicate retrieval issues

## Key files
- `deployment_manifest.md` — Current deployment state
- `verification_report.md` — Last verification results
- `framework/deployment/deploy_app.py` — AppDeployer (for endpoint management)
- `scripts/verify.py` — Run a fresh verification check
