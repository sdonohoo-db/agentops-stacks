# Databricks AgentOps Stacks

> **_NOTE:_** This feature is in [public preview](https://docs.databricks.com/release-notes/release-types.html).

This template uses a **flattened bundle layout**: project code lives at the bundle root. Generated projects have `databricks.yml`, `resources/`, `data_preparation/`, `agent_development/`, `agent_deployment/`, and related directories as direct children of the root (no project subdirectory).

This repo provides a customizable stack for starting new **AI agent** projects on Databricks that follow production best-practices out of the box.

Using AgentOps Stacks, you can quickly get started iterating on agent code (data preparation, agent development, evaluation, deployment) while ops engineers set up CI/CD and bundle resources, with an easy transition to production. The stack uses **MLflow 3.9** for GenAI features (tracing, evaluation with LLM-as-a-judge scorers, and deployment). More information: [MLflow 3.9 GenAI](https://mlflow.org/docs/3.9.0/genai/), [Databricks MLflow 3 for GenAI](https://docs.databricks.com/mlflow3/genai/).

The default stack includes:

| Component | Description |
|-----------|-------------|
| **Agent Code** | Example agent project structure: data preparation, agent development & evaluation, and deployment (including a Databricks App front end). |
| **Agent Resources as Code** | Bundle resources for data preparation jobs, agent jobs, and app deployment, defined through [Databricks CLI bundles](https://docs.databricks.com/dev-tools/cli/bundle-cli.html). |
| **CI/CD** | [GitHub Actions](template/{{.input_root_dir}}/.github/) or [Azure DevOps](template/{{.input_root_dir}}/.azure/) or [GitLab](template/{{.input_root_dir}}/.gitlab/) workflows to test and deploy agent code and resources. |

## Using AgentOps Stacks

### Prerequisites

- Python 3.8+
- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/databricks-cli.html) >= v0.288.0

### Start a new project

To create a new agent project, run:

```bash
databricks bundle init agentops-stacks
```

You can point the CLI at a local checkout of this repo:

```bash
databricks bundle init /path/to/agentops-stacks --output-dir /path/to/output
```

Parameters you will be prompted for (or pass via `--config-file`):

- **input_setup_cicd_and_project**: Set up both CI/CD and project (`CICD_and_Project`), project only (`Project_Only`), or CI/CD only (`CICD_Only`).
- **input_project_name**: Name of the agent project (default: `my_agentops_project`).
- **input_root_dir**: Root directory name (default: same as project name).
- **input_cloud**: Cloud provider (AWS, Azure, or GCP).
- **input_cicd_platform**: GitHub Actions, Azure DevOps, or GitLab (if not Project_Only).
- **input_databricks_staging_workspace_host** / **input_databricks_prod_workspace_host**: Staging and production workspace URLs (if not Project_Only).
- **input_default_branch** / **input_release_branch**: Default and release branch names.
- **input_read_user_group**: User group for READ permissions on project resources.
- **input_schema_name** / **input_staging_catalog_name** / **input_prod_catalog_name** / **input_test_catalog_name**: Unity Catalog schema and catalog names for agent data and resources.

## Relationship to MLOps Stacks

AgentOps Stacks is a **standalone** template for building agent bundles. It is independent of [MLOps Stacks](https://github.com/databricks/mlops-stacks): it does not depend on mlops-stacks, and it does not include the ML (training, batch inference, feature store, etc.) paths. Use **agentops-stacks** for AI agent projects and **mlops-stacks** for classical ML projects.

## License

See [LICENSE](LICENSE) in this repository.
