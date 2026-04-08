# GenAI Solution Components

Modular, composable building blocks for Databricks Asset Bundle projects. Each component is a self-contained set of DAB configuration, job workflows, and/or notebooks that can be incrementally added to an existing DAB and stitched together with other components.

## How components work

Each subdirectory contains:
- `databricks.yml` — only the resource snippet for this component (not a full bundle config)
- `notebooks/` — any Databricks notebooks the component needs (optional)
- `jobs/` — job/workflow definitions (optional)
- `README.md` — what it is, what it depends on, how to integrate it

To add a component to your DAB project:
1. Copy the component's `databricks.yml` snippet into your project's `resources/` directory
2. Copy any notebooks into your project's notebook directory
3. Add any required variables to your project's root `databricks.yml`
4. Run `databricks bundle validate` to confirm everything stitches together

Components are designed to compose — adding one should not break another.

## Available components

| Component | Description | Dependencies |
|---|---|---|
| `agent_app_base` | Databricks App with MLflow experiment, agent server scaffold | None |
| `vector_index` | Vector Search index with data ingestion pipeline | Unity Catalog table |

## Validation

Before a component is considered ready, it must pass:
1. Its `databricks.yml` snippet merges cleanly into a bundle with other components present
2. `databricks bundle validate` passes with the component added
3. `databricks bundle deploy` creates the expected resources
4. The component works alongside at least one other component in the same bundle
