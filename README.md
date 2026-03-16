# Databricks AgentOps Stacks

> **_NOTE:_** This feature is in [public preview](https://docs.databricks.com/release-notes/release-types.html).

AgentOps Stacks is a production-ready [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/cli/bundle-cli.html) template for AI agent projects. It generates a fully deployable project with data preparation, agent development, evaluation, model serving, and a chat UI — wired together with jobs, CI/CD workflows, and Unity Catalog resources out of the box.

The stack uses **MLflow 3.9** for GenAI tracing, LLM-as-a-judge evaluation, and agent deployment. See [MLflow 3.9 GenAI](https://mlflow.org/docs/3.9.0/genai/) and [Databricks MLflow 3 for GenAI](https://docs.databricks.com/mlflow3/genai/).

## What you get

| Component | Description |
|-----------|-------------|
| **Data Preparation** | Notebooks to ingest raw documents, chunk and preprocess them, and build a Databricks Vector Search index. |
| **Agent Development** | A LangGraph agent with Unity Catalog function tools and Vector Search retrieval, logged and registered via MLflow. |
| **Agent Evaluation** | MLflow `genai.evaluate()` with LLM-as-a-judge scorers against a held-out eval set. |
| **Model Serving** | `agents.deploy()` creates a Mosaic AI model serving endpoint with review app and feedback logging. |
| **Chat Interface** | Dash-based Databricks App connected to the serving endpoint. |
| **DAB Resources** | Jobs, registered model, experiment, and app defined as code in `resources/`. |
| **CI/CD** | GitHub Actions, Azure DevOps, or GitLab workflows for bundle validation, integration tests, and multi-environment deployment. |

## Prerequisites

- Python 3.10+
- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/databricks-cli.html) ≥ v0.288.0
- A Databricks workspace with Unity Catalog enabled (dev, staging, and prod)

## Quickstart

```bash
databricks bundle init agentops-stacks
```

Or point the CLI at a local checkout:

```bash
databricks bundle init /path/to/agentops-stacks --output-dir /path/to/output
```

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `input_setup_cicd_and_project` | `CICD_and_Project` / `Project_Only` / `CICD_Only` | `CICD_and_Project` |
| `input_project_name` | Project name (no spaces, dots, or slashes) | `my-agentops-project` |
| `input_root_dir` | Root directory name | same as project name |
| `input_cloud` | `aws` / `azure` / `gcp` | — |
| `input_cicd_platform` | `github_actions` / `azure_devops` / `gitlab` | — |
| `input_databricks_staging_workspace_host` | Staging workspace HTTPS URL | — |
| `input_databricks_prod_workspace_host` | Production workspace HTTPS URL | — |
| `input_default_branch` | Branch that triggers staging deployment | `main` |
| `input_release_branch` | Branch that triggers production deployment | `release` |
| `input_read_user_group` | Group granted CAN_VIEW on all resources | `users` |
| `input_schema_name` | Unity Catalog schema for agent data and models | — |
| `input_staging_catalog_name` | UC catalog for staging | `staging` |
| `input_prod_catalog_name` | UC catalog for production | `prod` |
| `input_test_catalog_name` | UC catalog for CI integration tests | `test` |

## Generated project structure

```
<project-root>/
├── databricks.yml              # Bundle root — targets, variables, resource includes
├── requirements.txt            # Data preparation dependencies
├── pytest.ini
├── test-requirements.txt
│
├── data_preparation/
│   ├── DataIngestion.py        # Scrape docs from a URL → raw Delta table
│   ├── DataPreprocessing.py    # Chunk and tokenize → preprocessed table
│   └── VectorSearch.py         # Build Databricks Vector Search index
│
├── agent_development/
│   ├── agent_requirements.txt  # Agent-specific dependencies (kept separate from data prep)
│   ├── Agent.py                # Create UC functions, log LangGraph agent with MLflow
│   ├── app.py                  # LangGraph ResponsesAgent implementation
│   └── AgentEvaluation.py      # mlflow.genai.evaluate() with LLM judges
│
├── agent_deployment/
│   ├── ModelServing.py         # agents.deploy() → Mosaic AI endpoint + review app
│   └── chat_interface_deployment/
│       ├── app.py              # Dash chat UI
│       ├── app.yaml            # Databricks App config
│       ├── DatabricksChatbot.py
│       └── requirements.txt
│
├── resources/
│   ├── data-preparation-resource.yml   # data-preprocessing-job (3 tasks)
│   ├── agent-resource.yml              # agent-development-job (3 tasks)
│   ├── agents-artifacts-resource.yml   # registered model + experiment
│   └── app-resource.yml                # Databricks App definition
│
├── .github/workflows/          # (or .azure/ or .gitlab/) CI/CD pipelines
├── docs/
└── tests/
```

## CI/CD overview

| Branch | Trigger | Action |
|--------|---------|--------|
| PR → `main` | CI | Bundle validate, unit tests, integration tests (deploys `test` target to staging workspace) |
| Merge to `main` | CD | Deploy `staging` target to staging workspace |
| Merge to `release` | CD | Deploy `prod` target to production workspace |

See the generated `docs/agentops-setup.md` for full CI/CD setup instructions.

## Contributing and testing

Install dev dependencies:

```bash
pip install -r dev-requirements.txt
```

Run the template generator tests (27 combinations: 3 clouds × 3 CI/CD platforms × 3 setup modes):

```bash
pytest tests/
```

The tests generate projects from the template using the Databricks CLI and validate structure, bundle resources, and workflow files.

## Relationship to MLOps Stacks

AgentOps Stacks is **standalone** and independent of [MLOps Stacks](https://github.com/databricks/mlops-stacks). It does not include classical ML paths (training, batch inference, feature store). Use **agentops-stacks** for AI agent projects and **mlops-stacks** for classical ML.

## License

See [LICENSE](LICENSE).
