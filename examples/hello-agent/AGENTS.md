# hello_agent

Instructions for AI coding agents working in this project. Tool-agnostic — applies to Claude Code, Cursor, Genie Code, GitHub Copilot, and any other assistant that reads project conventions.

## What this project is

An AgentOps Stacks project: a Databricks Asset Bundle scaffold for production-ready AI solutions. The structure, CI/CD wiring, and Unity Catalog configuration are pre-built; the user develops their AI solution on top.

## Project structure

- **`src/`** — user's AI solution code. Organize however suits the project; the scaffold doesn't prescribe an internal layout.
- **`resources/`** — DAB resource declarations (YAML). One file per concern. When adding a new resource (job, dashboard, app, pipeline, model serving, vector search), create a new YAML file here.
- **`tests/`** — pytest tests. `databricks-connect` is available as a dev dep for running against a remote cluster.
- **`docs/`** — project documentation. See `docs/setup.md` for the configuration guide.
- **`.agentops-stacks/`** — agentops-stacks metadata. Do not edit by hand.

## Unity Catalog conventions

One catalog per environment with a single schema per catalog:

- dev → `hello_agent_dev.hello_agent`
- staging → `hello_agent_staging.hello_agent`
- prod → `hello_agent_prod.hello_agent`

The schema holds all UC resources for the project: traces, models, artifacts, datasets.

Reference UC resources in code via env-specific values, not hardcoded names. The catalog name follows `<project>_<env>` by convention. When you add a job/app/endpoint resource, wire `DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA` into the resource's `env` block — bundle variables resolve there at deploy time:

```yaml
# in resources/<your-resource>.yml
env:
  DATABRICKS_CATALOG: ${var.catalog}
  DATABRICKS_SCHEMA: ${var.schema}
```

Then read at runtime:

```python
catalog = os.environ["DATABRICKS_CATALOG"]
schema = os.environ["DATABRICKS_SCHEMA"]
table = f"{catalog}.{schema}.my_table"
```

## MLflow 3 conventions

MLflow 3's default registry URI is `databricks-uc`. Model registration is automatically Unity Catalog–managed:

```python
import mlflow
mlflow.register_model(model_uri, name=f"{catalog}.{schema}.my_model")
```

### Trace storage in Unity Catalog

The bundled experiment resource (`resources/experiment.yml`) only sets `artifact_location` — traces land in the workspace-default location. To route traces to a UC table instead, configure it where you set the experiment in code:

```python
mlflow.set_experiment(
    name=f"/Shared/hello_agent_{env}",
    location_url=f"{catalog}.{schema}.traces",
)
```

### Experiment artifacts

Artifacts are logged to the UC volume defined in `resources/volumes.yml` automatically — the experiment's `artifact_location` already points at it.

## Recommended next steps

This is a fresh AgentOps Stacks scaffold. The CI/CD pipelines are wired but the production patterns below are not yet applied — they're applied as the solution develops.

### Patterns to apply (proactively offer these to the user)

| Pattern | What to add | Why |
|---|---|---|
| **Eval gates** | `evaluation/thresholds.yml` + `evaluation/gate.py` | CI workflows auto-detect them and refuse to promote when thresholds are breached |
| **Governance posture** | `governance/posture.md` (DASF mapping) and `governance/data_flows.md` | Prod-promotion workflow verifies posture is documented |
| **Monitoring** | Trace destination configured in code + alert rules per serving endpoint | Production observability and on-call response |

The agentops-stacks plugin will eventually provide interactive commands for each (`/add-eval-gate`, `/audit-governance`, `/add-monitoring`). Until the plugin is available, apply patterns manually — the conventions in this file are sufficient guidance.

### When a coding agent first opens this project

Offer the user:

1. **Verify configuration is complete.** Open `docs/setup.md` and confirm: UC catalogs exist, CLI profiles are configured, workspace hosts are filled in `databricks.yml`, CI/CD credentials are set up. Surface anything missing.
2. **Help them validate.** Run `databricks bundle validate -t dev --profile <dev-profile>`. Resolve any errors.
3. **Ask what they want to build.** The solution code goes in `src/`.
4. **Recommend the first production pattern.** Once they have working code, suggest adding eval gates (the lightest-weight production pattern and the one CI workflows are already wired for).

## Coding agent guidance

- In DAB resource YAML, reference catalog/schema via `${var.catalog}` and `${var.schema}` — never hardcode. In Python code at runtime, read them from env vars wired by the resource's `env` block (see UC conventions above).
- Do not add inline secrets to `databricks.yml` or workflow files. Use Databricks secret scopes or platform secret stores (GitHub Secrets, GitLab CI/CD variables, Azure DevOps variable groups).
- Production code must not use user-scoped workspace paths (`/Users/...`) — DAB production mode rejects them.
- Prefer YAML resource definitions over Python (pydabs) unless there's a specific reason; YAML stays readable for non-coders.
- Defer to ai-dev-kit's `databricks-bundles` skill (or equivalent platform-specific guidance) when authoring new DAB resources.
- When adding a new resource, also confirm the production patterns above are still complete — e.g., if the resource handles data subject to governance, update `governance/data_flows.md`.
