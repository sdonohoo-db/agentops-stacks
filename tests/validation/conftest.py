"""
Validation Test Configuration
==============================
Shared fixtures for end-to-end agent quality validation tests.
These tests run in the staging CI environment and require a full
Databricks workspace with Dev Catalog assets populated.
"""

import os
from pathlib import Path

import pytest

from framework.config import AgentOpsConfig, get_config
from framework.evaluation.dataset import load_eval_dataset


@pytest.fixture(scope="session")
def config() -> AgentOpsConfig:
    """AgentOpsConfig for the test session (staging environment)."""
    return get_config()


@pytest.fixture(scope="session")
def eval_dataset():
    """Load the reference eval dataset."""
    dataset_path = Path(__file__).parent.parent.parent / "reference_agent" / "eval" / "eval_dataset.jsonl"
    return load_eval_dataset(str(dataset_path))


@pytest.fixture(scope="session")
def requires_databricks():
    """Skip test if not running in a Databricks-connected environment."""
    if not os.environ.get("DATABRICKS_HOST"):
        pytest.skip("Requires DATABRICKS_HOST (Databricks environment)")
