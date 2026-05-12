"""Eval gate for hello-agent.

Runs `mlflow.genai.evaluate()` against the registered agent and the golden
dataset, then checks results against thresholds in `evaluation/thresholds.yml`.
Exits non-zero if any blocking threshold is breached.

Invoked by the CI workflow when `evaluation/thresholds.yml` is present.
Run locally with: `uv run python evaluation/gate.py`.
"""
import json
import os
import sys
from pathlib import Path

import mlflow
import pandas as pd
import yaml
from mlflow.genai import evaluate
from mlflow.genai.scorers import Correctness, Safety

HERE = Path(__file__).parent
ROOT = HERE.parent

# Map scorer config name -> scorer class. Extend as new scorers are wired in.
SCORER_REGISTRY = {
    "Safety": Safety,
    "Correctness": Correctness,
}


def load_config() -> dict:
    with (HERE / "thresholds.yml").open() as f:
        return yaml.safe_load(f)


def load_dataset(path: str) -> pd.DataFrame:
    rows = []
    with (ROOT / path).open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def resolve_model_uri(template: str) -> str:
    catalog = os.environ.get("DATABRICKS_CATALOG")
    schema = os.environ.get("DATABRICKS_SCHEMA")
    if not catalog or not schema:
        sys.exit(
            "::error::DATABRICKS_CATALOG and DATABRICKS_SCHEMA must be set "
            "(wired by the DAB target's variables block; export manually for local runs)."
        )
    return template.format(catalog=catalog, schema=schema)


def build_scorers(cfg: list[dict]) -> list:
    scorers = []
    for entry in cfg:
        cls = SCORER_REGISTRY.get(entry["name"])
        if cls is None:
            sys.exit(f"::error::Unknown scorer '{entry['name']}'. Add it to SCORER_REGISTRY in gate.py.")
        scorers.append(cls())
    return scorers


def predict_fn_for(model) -> callable:
    def predict(query: str) -> str:
        result = model.predict(pd.DataFrame([{"query": query}]))
        return result[0]["response"] if isinstance(result, list) else result
    return predict


def main() -> None:
    cfg = load_config()
    model_uri = resolve_model_uri(cfg["model"]["uri"])
    dataset = load_dataset(cfg["dataset"]["path"])
    scorers = build_scorers(cfg["scorers"])

    print(f"Loading model: {model_uri}")
    try:
        model = mlflow.pyfunc.load_model(model_uri)
    except Exception as exc:
        sys.exit(
            f"::error::Failed to load model from {model_uri}: {exc}\n"
            "Run notebooks/register_agent.py to register the agent and set the @champion alias."
        )

    print(f"Evaluating against {len(dataset)} examples with {len(scorers)} scorer(s)")
    result = evaluate(data=dataset, predict_fn=predict_fn_for(model), scorers=scorers)

    failures = []
    for entry in cfg["scorers"]:
        # MLflow aggregates scorer results into metrics keyed like '<name>/mean'.
        # Adjust the suffix here if MLflow renames it in future versions.
        metric_key = f"{entry['name'].lower()}/mean"
        score = result.metrics.get(metric_key)
        if score is None:
            print(f"::warning::Metric '{metric_key}' not in evaluate result; check scorer name.")
            continue
        line = f"{entry['name']}: {score:.3f} (threshold {entry['threshold']:.3f}, {entry['severity']})"
        if score < entry["threshold"] and entry["severity"] == "blocking":
            print(f"::error::FAIL — {line}")
            failures.append(line)
        elif score < entry["threshold"]:
            print(f"::warning::{line}")
        else:
            print(f"PASS — {line}")

    if failures:
        sys.exit(1)
    print("Eval gate: all blocking thresholds met.")


if __name__ == "__main__":
    main()
