# agent_app_base

Base Databricks App component with MLflow experiment and agent server scaffold.

## What it provides

- Databricks App resource definition with `source_code_path`, command, and standard env vars
- MLflow experiment resource for tracing and evaluation
- App-to-experiment resource binding
- Standard agent server entry point (`uv run start-app`)

## Dependencies

None. This is the foundational component — other components add capabilities on top.

## Files

- `databricks.yml` — app + experiment resource definitions and variables
- `app.yaml` — Databricks App runtime configuration
- `agent_server/start_server.py` — AgentServer bootstrap (common across all agent types)
- `agent_server/agent.py` — placeholder agent with `@invoke()` / `@stream()` contract

## Integration

1. Copy `databricks.yml` contents into your project's `resources/` directory (or add as an include)
2. Copy `app.yaml` to your project root
3. Copy `agent_server/` to your project
4. Add `app_name` variable to your root `databricks.yml` if not already present
5. Ensure `sync.include` covers `agent_server/**`, `app.yaml`, `pyproject.toml`

## Variables

| Variable | Description | Default |
|---|---|---|
| `app_name` | App name (lowercase, numbers, dashes) | project name with dashes |
