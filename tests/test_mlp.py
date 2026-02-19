from utils import (
    databricks_cli,
    generated_project_dir,
    parametrize_by_project_generation_params,
)
import pytest
import os


@pytest.mark.parametrize(
    "profile",
    [
        "databricks-prod",
        "databricks-staging",
        "databricks-test",
        "databricks-dev",
        "local",
    ],
)
@parametrize_by_project_generation_params
def test_mlp_yaml_valid(generated_project_dir, profile):
    # AgentOps Stacks does not include MLflow Recipes (no training/ folder). Skip.
    project_dir = generated_project_dir / "my-agentops-project"
    training_notebooks = project_dir / "my_agentops_project" / "training" / "notebooks"
    if not training_notebooks.exists():
        return
    from mlflow.recipes import Recipe  # MLflow 3.9; only when recipes exist

    os.chdir(training_notebooks)
    Recipe(profile)
