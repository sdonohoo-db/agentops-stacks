---
title: AgentOps Best Practices
description: Opinionated best practices for developing and operating AI agents on Databricks
category: guidance
tags: [best-practices, evaluation, observability, ci-cd, safety]
related_docs:
  - docs/evaluation.md
  - docs/monitoring.md
  - docs/agent-development.md
---

# AgentOps Best Practices

## Evaluation-Driven Development

**Define eval datasets before building agents.** Your eval dataset is your specification — it describes what "good" looks like. If you build first and eval later, you're optimizing blind.

```python
# Good: eval dataset exists before agent development begins
eval_df = load_eval_dataset("eval/my_agent.jsonl")
evaluator = AgentEvaluator(agent_name="my_agent")
result = evaluator.run(agent=my_agent, eval_data=eval_df)
assert result.passed()
```

**Never lower thresholds to make tests pass.** If your agent fails correctness, fix the agent — don't lower `correctness` to 0.5.

**Use 20+ eval samples.** Fewer than 10 samples gives unreliable signal. 20 is the minimum for development; 100+ for staging gates.

## Observability First

**Trace everything.** Every agent interaction must produce an MLflow trace. Use `@mlflow.trace` on your `_invoke()` method and `mlflow.langchain.autolog()` for LangChain components.

```python
@mlflow.trace(name="my_agent.invoke", span_type="AGENT")
def _invoke(self, messages, context=None):
    # All sub-calls are traced automatically with autolog
    ...
```

**Log to the right experiment.** Use `set_experiment_for_env()` so traces land in `/AgentOps/<env>/<agent_name>`. Never use the default experiment.

**Capture human feedback.** SME feedback logged to MLflow creates an audit trail and a future fine-tuning signal. Don't let review happen outside the system.

## Safety and Governance

**Never write to Prod Catalog from dev.** Unity Catalog enforces this, but also never attempt it in code. Dev code reads prod data for baseline comparison only.

**Always use the `@champion` alias.** Production endpoints reference `@champion`. Set it only after passing evaluation. Never set it manually on unvalidated model versions.

**Secret management via Databricks Secrets.** Never hardcode tokens, API keys, or connection strings. Use `get_secret(scope, key)` from `framework/utils/databricks_utils.py`.

## CI/CD Discipline

**Every commit triggers CI.** Don't skip the staging gate by merging directly to `main`. The three-tier test suite exists for a reason.

**Fix failures, don't skip them.** If validation tests fail in staging, fix the underlying issue. Don't bypass with `--force` or by adjusting thresholds.

**Check the manifest after deployment.** Every deployment generates `deployment_manifest.md`. Read it. Verify it with `scripts/verify.py`.

## Agent Design

**Keep agents focused.** Each agent should have one well-defined capability. Use the router for multi-capability systems, not a single all-purpose agent.

**Document your eval dataset reasoning.** Add comments or metadata to eval samples explaining *why* that sample tests an important behavior.

**Handle retrieval failures gracefully.** RAG agents should tell users clearly when the knowledge base doesn't have enough information, rather than hallucinating.

**Test safety explicitly.** Your eval dataset should include adversarial prompts. Safety score must be 1.0 (100% safe responses).

## Production Operations

**Monitor trace quality, not just uptime.** An endpoint can be READY but serving degraded quality responses. MLflow traces are your quality monitoring signal.

**Establish baselines in staging.** Record your staging eval metrics before promoting. Compare production metrics to this baseline to detect drift.

**Plan for rollback.** The `@champion` alias makes rollback easy: re-point it to the previous version. Know which version is currently serving before each deployment.
