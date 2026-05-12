# Evaluation pattern — hello-agent

The evaluation pattern applied to the Hello Agent. For the pattern *contract*
(what `thresholds.yml` and `gate.py` are expected to provide across all
projects), see `projectdocs/patterns/evaluation.md` in the agentops-stacks-v2
repo.

## What this evaluates

The Hello Agent registered to UC at `<catalog>.<schema>.hello_agent@champion`,
evaluated against `golden_dataset.jsonl` using two scorers:

- **Safety** (blocking, threshold 1.0) — every response must be flagged Safe.
- **Correctness** (warning, threshold 0.8) — ≥ 80% of responses should match
  the expected response.

The gate fails on any blocking-severity breach.

## Files

- `thresholds.yml` — config: model URI, dataset path, scorer list with thresholds.
- `golden_dataset.jsonl` — eval inputs and expected responses, one JSON object
  per line.
- `gate.py` — loads config, runs `mlflow.genai.evaluate()`, fails on blocking
  threshold breach.

## Running

**Locally:**

```bash
export DATABRICKS_CATALOG=<your-dev-catalog>
export DATABRICKS_SCHEMA=<your-schema>
uv run python evaluation/gate.py
```

**In CI:**

The PR-check workflow auto-detects `thresholds.yml` and runs `gate.py` after
`bundle validate` passes. Catalog/schema come from the DAB target's variables
block.

## Prerequisites

The model must already be registered to UC with the `@champion` alias. Run
`notebooks/register_agent.py` once to do this. The gate prints a helpful
error if the model isn't found.

## Adapting for your own agent

1. Replace `golden_dataset.jsonl` with your project's golden dataset.
2. Update `model.uri` in `thresholds.yml` to point at your registered model.
3. Add/configure scorers in `thresholds.yml`. If you add a scorer not in
   `SCORER_REGISTRY` in `gate.py`, extend the registry first.
4. Tune thresholds based on baseline runs.
