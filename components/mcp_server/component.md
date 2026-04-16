---
name: mcp_server
description: MCP server deployed as a Databricks App using FastMCP.
category: mcp
requires: []
optional_with: []

copies:
  - src: server/
    dest: server/
  - src: resources/app-resource.yml
    dest: resources/app-resource.yml
  - src: app.yaml
    dest: app.yaml

modifies:
  - target: databricks.yml
    action: append_list
    path: sync.include
    values:
      - "server/**"
      - "app.yaml"

  - target: pyproject.toml
    action: add_dependencies
    values:
      - "fastapi>=0.129.0"
      - "uvicorn>=0.41.0"
      - "fastmcp>=2.0.0"
      - "databricks-sdk>=0.56.0"

  - target: pyproject.toml
    action: add_entry_points
    values:
      custom-mcp-server: "server.main:main"

platform_resources:
  creates: [app]
  requires: []

variables: []

data_flows:
  - data: MCP tool call request/response payloads
    storage: Databricks App logs
    contains_customer_data: true
  - data: MCP server source code
    storage: Databricks App (workspace storage)
    contains_customer_data: false

compliance:
  feature_status: GA
  hipaa_csp_supported: true
  safely_removable: true
  security_defaults: >
    App runs with workspace service principal identity. User identity is
    forwarded via x-forwarded-access-token header for OBO access patterns.
    No data leaves the workspace boundary.
  customer_actions:
    - Configure app permissions to restrict access to authorized users
    - Configure identity propagation (OBO) if the MCP server accesses user-scoped resources

docs:
  - title: Databricks Apps documentation
    url: https://docs.databricks.com/en/dev-tools/databricks-apps/index.html
  - title: FastMCP documentation
    url: https://gofastmcp.com/
---

MCP server deployed as a Databricks App using FastMCP. Provides a FastAPI + FastMCP
application with tool registration, health check, user auth forwarding, and DAB
resource definitions.

## What you get

- `server/app.py` — FastAPI + FastMCP application setup
- `server/main.py` — uvicorn entry point
- `server/tools.py` — tool definitions (health check + get_current_user scaffold)
- `server/utils.py` — workspace client helpers with user auth forwarding
- `resources/app-resource.yml` — Databricks App resource definition
- `app.yaml` — app runtime configuration

## After installation

1. Add your tools in `server/tools.py`
2. To test locally: `uv sync && uv run custom-mcp-server`
3. Run `databricks bundle deploy -t dev` to deploy
