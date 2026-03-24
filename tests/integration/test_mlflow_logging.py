"""
Integration Tests: MLflow Logging
Tests MLflow experiment setup and metric logging against a real MLflow instance.
Requires: DATABRICKS_HOST and DATABRICKS_TOKEN env vars, or active cluster.
"""

import os

import mlflow
import pytest

from framework.config import get_config
from framework.utils.mlflow_utils import (
    get_or_create_experiment,
    log_eval_results,
    set_experiment_for_env,
)

# Skip if not in a Databricks environment
requires_databricks = pytest.mark.skipif(
    not os.environ.get("DATABRICKS_HOST"),
    reason="Requires DATABRICKS_HOST env var (Databricks environment)",
)


@requires_databricks
class TestMLflowExperimentSetup:
    def test_get_or_create_experiment_returns_id(self):
        cfg = get_config()
        exp_id = get_or_create_experiment(
            name="/AgentOps/integration_test",
            config=cfg,
        )
        assert isinstance(exp_id, str)
        assert len(exp_id) > 0

    def test_get_or_create_experiment_idempotent(self):
        cfg = get_config()
        exp_id_1 = get_or_create_experiment(name="/AgentOps/idempotent_test", config=cfg)
        exp_id_2 = get_or_create_experiment(name="/AgentOps/idempotent_test", config=cfg)
        assert exp_id_1 == exp_id_2

    def test_set_experiment_for_env(self):
        cfg = get_config()
        exp_id = set_experiment_for_env("integration_test_agent", config=cfg)
        assert isinstance(exp_id, str)

    def test_log_eval_results_in_run(self):
        cfg = get_config()
        set_experiment_for_env("integration_test_agent", config=cfg)

        with mlflow.start_run(run_name="test_log_eval") as run:
            log_eval_results(
                results={
                    "metrics": {
                        "correctness": 0.85,
                        "groundedness": 0.92,
                        "relevance": 0.88,
                    }
                },
                config=cfg,
            )
            run_id = run.info.run_id

        # Verify metrics were logged
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        run_data = client.get_run(run_id)
        assert "eval.correctness" in run_data.data.metrics
        assert abs(run_data.data.metrics["eval.correctness"] - 0.85) < 0.001
