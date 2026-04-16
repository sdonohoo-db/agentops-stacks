---
name: agent_app
description: Agent backend deployed as a Databricks App with MLflow experiment.
category: agent
requires: []
optional_with: [vector_search]

copies:
  - src: agent_server/
    dest: agent_server/
  - src: resources/app-resource.yml
    dest: resources/app-resource.yml
  - src: app.yaml
    dest: app.yaml

modifies:
  - target: databricks.yml
    action: append_list
    path: sync.include
    values:
      - "agent_server/**"
      - "app.yaml"

  - target: pyproject.toml
    action: add_dependencies
    values:
      - "fastapi>=0.129.0"
      - "uvicorn>=0.41.0"
      - "mlflow>=3.10.0"
      - "databricks-agents>=1.9.3"

  - target: pyproject.toml
    action: add_entry_points
    values:
      start-server: "agent_server.start_server:main"

platform_resources:
  creates: [app, experiment]
  requires: []

variables: []

data_flows:
  - data: agent request/response payloads
    storage: MLflow experiment (traces)
    contains_customer_data: true
  - data: agent source code
    storage: Databricks App (workspace storage)
    contains_customer_data: false

compliance:
  feature_status: GA
  hipaa_csp_supported: true
  safely_removable: true
  security_defaults: >
    App runs with workspace service principal identity. MLflow experiment
    stores traces in the user's workspace. No data leaves the workspace boundary.
  customer_actions:
    - Configure app permissions to restrict access to authorized users
    - Review MLflow experiment permissions if traces contain sensitive data
    - Configure identity propagation (OBO) if the agent accesses user-scoped resources

docs:
  - title: Databricks Apps documentation
    url: https://docs.databricks.com/en/dev-tools/databricks-apps/index.html
  - title: MLflow AgentServer
    url: https://mlflow.org/docs/latest/genai/agent-server.html
---

Agent backend deployed as a Databricks App. Provides the MLflow AgentServer with
`@invoke()` / `@stream()` contract, an MLflow experiment for tracing, and the DAB
resource definitions for the app and experiment.

This component deploys the agent API only — no browser UI.

## What you get

- `agent_server/agent.py` — scaffold with `@invoke()` and `@stream()` handlers
- `agent_server/start_server.py` — MLflow AgentServer bootstrap
- `resources/app-resource.yml` — Databricks App + experiment resource definitions
- `app.yaml` — app runtime configuration

## After installation

1. Edit `agent_server/agent.py` with your agent logic
2. To test locally: `uv sync && uv run start-server`
3. Run `databricks bundle deploy -t dev` to deploy
