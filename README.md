# AgentOps Stacks

A Databricks Asset Bundle (DAB) template for AI agent projects. Generates a production-ready project structure with CI/CD and deployment to Databricks Apps.

## What You Get

- **Databricks App deployment** — your agent runs inside a Databricks App via MLflow AgentServer
- **Agent framework flexibility** — choose any agent template from [databricks/app-templates](https://github.com/databricks/app-templates) at setup time
- **Evaluation pipeline** — automated agent evaluation with quality gates that block deployment when metrics don't meet thresholds
- **CI/CD workflows** — GitHub Actions, Azure DevOps, or GitLab pipelines for bundle validation and deployment
- **Multi-environment targets** — dev, staging, prod, and test configurations

## Prerequisites

- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/install.html) v0.288.0 or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Python 3.11+
- A Databricks workspace with Unity Catalog enabled

## Quick Start

### 1. Initialize the project

```bash
databricks bundle init https://github.com/sdonohoo-db/agentops-stacks
```

You'll be asked 5 questions: project name, cloud provider, CI/CD platform, and setup scope.

### 2. Select your agent framework

```bash
cd my_agentops_project
uv run setup
```

This queries GitHub for the latest agent templates and presents a menu. Available frameworks include LangGraph, OpenAI Agents SDK, multi-agent orchestrators, and more.

### 3. Configure your workspace

Edit `databricks.yml` and set the workspace host URLs and Unity Catalog configuration for each target environment.

### 4. Deploy

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

## Project Structure

After initialization and setup, your project looks like this:

```
my_agentops_project/
├── databricks.yml              # Bundle configuration and target environments
├── app.yaml                    # Databricks App configuration
├── pyproject.toml              # Python project and dependencies
├── agent_server/               # Agent code (installed by setup)
│   ├── agent.py                # Agent logic with @invoke/@stream handlers
│   ├── start_server.py         # AgentServer bootstrap
│   └── utils.py                # Helper functions
├── scripts/
│   ├── setup.py                # Framework selection and installation
│   └── start_app.py            # Local dev server + chat frontend
├── resources/                  # DAB resource definitions
│   └── app-resource.yml        # Databricks App resource
└── .github/workflows/          # CI/CD (or .azure/ or .gitlab/)
```

## How It Works

### Architecture

AgentOps Stacks separates concerns into two layers:

1. **Operations layer** (this template) — bundle configuration, CI/CD, evaluation pipelines, deployment targets. This is what `databricks bundle init` generates.

2. **Agent layer** (from app-templates) — the actual agent code that handles user requests. This is what `uv run setup` installs. Because it pulls from the official [databricks/app-templates](https://github.com/databricks/app-templates) repo, you always get the latest patterns.

### Databricks Asset Bundles

A DAB is a project format that lets you define Databricks resources (jobs, apps, models, experiments) as YAML configuration alongside your code. The Databricks CLI deploys everything together. Think of it as infrastructure-as-code for Databricks.

Key concepts:
- **`databricks.yml`** — the bundle root configuration. Defines variables, resource includes, and deployment targets.
- **Targets** — named environments (dev, staging, prod) with different workspace URLs and variable values.
- **Resources** — YAML files in `resources/` that define jobs, apps, registered models, and experiments.
- **`databricks bundle deploy`** — deploys all resources to the specified target workspace.

### Agent Deployment

Your agent runs inside a [Databricks App](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html) using MLflow's AgentServer. The app serves your agent on an HTTP endpoint with a built-in chat UI.

The deployment flow:
1. `databricks bundle deploy` creates the app resource in your workspace
2. The app starts and runs your agent server via `uv run start-app`
3. Users interact with the agent through the app's chat interface

### Evaluation Pipeline

The agent development job runs two tasks in sequence:
1. **AgentDevelopment** — creates the agent, logs it to MLflow, registers in Unity Catalog
2. **AgentEvaluation** — evaluates against a benchmark dataset using LLM-as-a-judge scorers. If metrics fall below configured thresholds, the job fails.

Threshold presets:
- **relaxed** (dev) — `correctness=0.7, groundedness=0.8, relevance=0.7, safety=1.0`
- **strict** (staging/prod) — `correctness=0.9, groundedness=0.95, relevance=0.85, safety=1.0`

## CI/CD

The template generates CI/CD workflows for your chosen platform. The pipeline:

1. **On PR** — validates the bundle configuration for staging and prod targets
2. **On merge to main** — deploys to staging
3. **On merge to release** — deploys to production

### Required Secrets

**GitHub Actions (AWS/GCP):**
- `STAGING_WORKSPACE_TOKEN`, `PROD_WORKSPACE_TOKEN`

**GitHub Actions (Azure):**
- `STAGING_AZURE_SP_TENANT_ID`, `STAGING_AZURE_SP_APPLICATION_ID`, `STAGING_AZURE_SP_CLIENT_SECRET`
- `PROD_AZURE_SP_TENANT_ID`, `PROD_AZURE_SP_APPLICATION_ID`, `PROD_AZURE_SP_CLIENT_SECRET`

See the generated CI/CD README in `.github/workflows/README.md` (or equivalent) for platform-specific setup.

## Local Development

```bash
# Install dependencies
uv sync

# Start the agent server locally
uv run start-server

# Start with chat UI (clones frontend on first run)
uv run start-app
```

## Customization

### Changing branch names

CI/CD workflows default to `main` (staging deploys) and `release` (prod deploys). Edit the branch triggers in your CI/CD workflow files to change these.

### Adding app resources

If your agent needs access to serving endpoints, UC functions, or databases, add them to the `resources:` section in `resources/app-resource.yml`. See the [Databricks Apps documentation](https://docs.databricks.com/en/dev-tools/databricks-apps/app-resources.html) for available resource types.

### Docker image (GitLab)

GitLab pipelines use `databricksfieldeng/mlopsstacks:latest` by default. Change the `image:` line in `.gitlab/pipelines/*.yml` files to use a different image.
