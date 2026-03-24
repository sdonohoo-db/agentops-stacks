---
title: Monitoring
description: Monitor production AgentOps deployments using MLflow traces, metrics, endpoint health checks, and quality dashboards
category: monitoring
tags: [monitoring, mlflow-tracing, observability, endpoint-health, quality, production]
related_docs: [deployment.md, evaluation.md, best-practices.md]
---

# Monitoring

Every AgentOps deployment emits MLflow traces for every agent invocation. These traces are the primary observability signal for production quality, latency, and error rates.

---

## What Gets Traced

| Signal | Source | Where |
|---|---|---|
| Every `predict()` call | `@mlflow.trace` on `AgentBase.predict()` | MLflow Traces UI |
| LangChain chain calls | `mlflow.langchain.autolog()` | MLflow Traces UI |
| Tool invocations | Manual `mlflow.start_span()` | MLflow Traces UI |
| Retrieval operations | LangChain autolog | MLflow Traces UI |
| Eval metrics | `mlflow.genai.evaluate()` | MLflow Experiments UI |
| Endpoint latency + errors | Databricks Model Serving | Databricks Serving UI |

---

## MLflow Tracing

Every `AgentBase.predict()` call produces a trace with:
- Input messages
- Routed agent name (for multi-agent)
- Retrieved context (for RAG agents)
- Final response
- Duration per span

### Viewing traces

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db  # local
```

In the Databricks workspace:
- Navigate to **Experiments → agentops_prod**
- Select **Traces** tab
- Filter by `agentops.env=prod` tag

### Querying traces programmatically

```python
import mlflow
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Get recent traces
traces = client.search_traces(
    experiment_ids=["your_experiment_id"],
    filter_string="attributes.status = 'OK'",
    max_results=100,
    order_by=["timestamp_ms DESC"],
)

for trace in traces:
    print(trace.info.request_id, trace.info.execution_time_ms)
```

### Autologging setup

Enable at application start (in `reference_agent/app.py` or at job start):

```python
from framework.utils.mlflow_utils import setup_autologging

setup_autologging(log_models=False)
# All LangChain calls now traced automatically
```

---

## Experiment Structure

MLflow experiments follow this naming convention:

```
/AgentOps/dev/rag_agent          ← dev evaluation runs
/AgentOps/dev/summarization_agent
/AgentOps/staging/rag_agent      ← CI validation runs
/AgentOps/prod/rag_agent         ← prod inference traces
```

Use `set_experiment_for_env()` to configure consistently:

```python
from framework.utils.mlflow_utils import set_experiment_for_env

# In any DAB job or serving endpoint startup code:
set_experiment_for_env("rag_agent")
# Sets experiment to /AgentOps/{env}/rag_agent
```

---

## Endpoint Health Monitoring

The `/monitor-deployment` Claude Code skill and MCP tool run `scripts/verify.py` to check:

1. **Job status** — Every DAB workflow's last run state (from Databricks Jobs API)
2. **UC model existence** — `@champion` alias is set and resolves to a version
3. **Endpoint state** — Model Serving endpoint returns `state.ready = READY`
4. **Test inference** — One request sent; must return HTTP 200

```bash
# Manual health check
python scripts/verify.py --target prod --test-inference

# Via Claude Code skill
/monitor-deployment
```

Output (`verification_report.md`):

```markdown
---
verification_timestamp: 2026-03-20T14:45:00Z
overall_status: PASSED
---

## Component Health
| Component | Status | Details |
|---|---|---|
| data_preparation workflow | ✅ PASSED | Last run: SUCCESS (2026-03-20) |
| agent_development workflow | ✅ PASSED | Last run: SUCCESS (2026-03-20) |
| app_deployment workflow | ✅ PASSED | Last run: SUCCESS (2026-03-20) |
| rag_agent UC model | ✅ PASSED | @champion → version 3 |
| multi_agent_app endpoint | ✅ PASSED | READY |
| Test inference | ✅ PASSED | Response received in 1.2s |
```

---

## Quality Monitoring in Production

For ongoing quality tracking, run a nightly or weekly mini-evaluation using the batch inferencing workflow:

```python
from framework.evaluation.evaluator import AgentEvaluator
from framework.utils.mlflow_utils import set_experiment_for_env
from framework.config import get_config

cfg = get_config()  # AGENTOPS_ENV=prod
set_experiment_for_env("rag_agent")

# Load a sample of recent production queries
eval_df = load_prod_query_sample(n=50)  # Your sampling logic

evaluator = AgentEvaluator(agent_name="rag_agent_prod_monitor")
result = evaluator.run(agent=rag_agent, eval_data=eval_df)

# Alert if quality drops
if not result.passed():
    # Trigger alert / create GitHub issue / post to Slack
    print(f"QUALITY ALERT: {result.summary()}")
```

---

## Batch Inferencing Traces

The batch inferencing workflow (`bundle/resources/batch_inferencing_workflow.yml`) logs traces and metrics to the prod MLflow experiment on every run:

```python
# framework/batch_inferencing/batch_inferencer.py
import mlflow

with mlflow.start_run(run_name="batch_inference_daily"):
    mlflow.log_metric("rows_processed", total_rows)
    mlflow.log_metric("errors", error_count)
    mlflow.log_metric("avg_latency_ms", avg_latency)
    mlflow.log_metric("success_rate", success_rate)
```

---

## Alert Conditions to Watch For

| Condition | Threshold | Action |
|---|---|---|
| Endpoint not READY | Any | Page oncall, rollback |
| Test inference fails | Any | Page oncall, rollback |
| `correctness` drops | < 0.75 | Investigate traces, consider rollback |
| `groundedness` drops | < 0.85 | Check Vector Search index freshness |
| Latency P99 | > 10s | Check endpoint workload size |
| Error rate | > 5% | Check endpoint logs |

---

## Viewing Eval Metrics Over Time

MLflow tracks evaluation metrics per run. Compare across runs:

```python
client = MlflowClient()

# Get all eval runs for rag_agent in prod
runs = client.search_runs(
    experiment_ids=["prod_rag_agent_experiment_id"],
    filter_string="tags.agentops.env = 'prod'",
    order_by=["start_time DESC"],
)

for run in runs[:10]:
    metrics = run.data.metrics
    print(
        f"{run.info.run_name}: "
        f"correctness={metrics.get('eval.correctness', 'N/A'):.2f} "
        f"groundedness={metrics.get('eval.groundedness', 'N/A'):.2f}"
    )
```

---

## Refreshing the Vector Search Index

If retrieval quality drops, the Vector Search index may be stale. Re-trigger the data preparation workflow:

```bash
databricks jobs run-now --job-id <data_preparation_job_id>
```

Or sync the index manually:

```python
from framework.data_preparation.vector_search_indexing import VectorSearchIndexer

indexer = VectorSearchIndexer(
    endpoint_name="agentops-vs-endpoint",
    index_name="agentops_prod.agentops.agentops_vs_index",
    source_table="agentops_prod.agentops.chunks",
)
indexer.sync()  # Triggers Delta Sync
```

---

## Using the `/monitor-deployment` Skill

```
/monitor-deployment
```

The skill:
1. Reads `deployment_manifest.md`
2. Runs `scripts/verify.py --test-inference`
3. Reads `verification_report.md`
4. Surfaces the top issues with recommendations

Pass `run_verification=True` to the MCP tool for live checks:

```python
# Via MCP
result = monitor_deployment(target="prod", run_verification=True)
```
