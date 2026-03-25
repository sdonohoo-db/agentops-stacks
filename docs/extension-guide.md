---
title: AgentOps Extension Guide
description: How to add new agents, data sources, test types, and monitoring to AgentOps
category: development
tags: [extension, agents, customization, patterns]
related_docs:
  - docs/agent-development.md
  - docs/best-practices.md
  - docs/ci-cd.md
---

# AgentOps Extension Guide

## Adding a New Agent

The fastest path is the scaffold script:

```bash
python scripts/scaffold.py \
  --name my_agent \
  --description "Does X using Y" \
  --type rag  # or: summarization, generic
```

This creates:
- `reference_agent/agents/my_agent/agent.py` — implement `_invoke()` here
- `reference_agent/agents/my_agent/tools.py` — register UC tools here
- `reference_agent/eval/eval_my_agent.jsonl` — add eval samples here
- `bundle/resources/my_agent_workflow.yml` — DAB workflow (auto-configured)

### Wire the agent into the router

In `reference_agent/router/router.py`:

```python
from reference_agent.agents.my_agent.agent import MyAgent

router.register_agent(
    name="my_agent",
    agent=MyAgent(config=cfg),
    description="What this agent does and when to route to it",
    keywords=["trigger", "words", "for", "fast", "routing"],
)
```

### Add tools

In `reference_agent/agents/my_agent/tools.py`, add `ToolSpec` registrations:

```python
registry.register(ToolSpec(
    name="my_tool",
    description="What this tool does",
    input_params="query STRING, top_k INT DEFAULT 5",
    return_type="STRING",
    body="return query.upper()  # replace with real logic",
))
```

### Add eval samples

Add at least 20 samples to `eval/eval_my_agent.jsonl`:

```jsonl
{"request": "test question", "expected_response": "expected answer", "metadata": {"category": "general"}}
```

## Adding a New Data Source

Add a new ingestion class in `framework/data_preparation/ingestion.py`:

```python
class MyAPIIngestion(DataIngestionBase):
    def ingest(self) -> IngestionResult:
        # Fetch from your API
        # Write to self.target_table with schema: id, content, metadata
        ...
```

Then add a task to `bundle/resources/data_preparation_workflow.yml`:

```yaml
- task_key: my_api_ingestion
  description: Ingest from My API
  depends_on:
    - task_key: data_ingestion  # or run in parallel
  job_cluster_key: data_prep_cluster
  python_wheel_task:
    package_name: agentops_framework
    entry_point: run_my_api_ingestion
```

## Adding a New Test Type in Staging

Add a new test file in `tests/validation/` or `tests/integration/`:

```python
# tests/validation/test_my_custom_check.py
class TestMyCustomCheck:
    def test_something_important(self, config):
        # Your check
        assert ...
```

Add a new job to `.github/workflows/ci.yml` following the same pattern as the existing test jobs.

## Adding Monitoring/Alerting

Extend `scripts/verify.py` to add new health checks:

```python
def check_custom_metric(client, result: VerificationResult) -> None:
    # Query MLflow or Databricks for your metric
    # Call result.add("My Check", passed, "details")
    ...
```

For production alerting, connect MLflow experiment data to Databricks Alerts or your existing monitoring stack. The `batch_inferencing_workflow.yml` runs daily — add an alert task after batch inference to check quality metrics.

## Multi-Account Promotion

The current architecture is single-account. To split prod into a separate account:

1. Create a separate Unity Catalog in the prod account
2. Configure cross-account Delta Sharing for catalog access
3. Add a new `prod_cross_account.yml` target in `bundle/targets/`
4. Update `cd.yml` to deploy to both accounts

This is an advanced pattern — start single-account and migrate only if required by security policy.
