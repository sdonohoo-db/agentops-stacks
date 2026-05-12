# Hello Agent — agentops-stacks v2 example

A worked example of the agentops-stacks v2 evaluation pattern applied to a
deliberately trivial agent. The Hello Agent does almost nothing — it echoes
the user's input back with a fixed greeting. It exists to demonstrate the
closed loop (register → evaluate → gate) end-to-end without distracting
solution complexity.

For broader context (what examples are, why they're separate from the
scaffold), see [../README.md](../README.md).

## What's in this example

- A complete v2 scaffold (Azure + GitHub Actions) — same shape as
  `databricks bundle init` produces.
- `src/hello_agent.py` — a minimal MLflow pyfunc agent.
- `notebooks/register_agent.py` — one-time setup that registers the agent
  to UC Models with the `@champion` alias.
- `evaluation/` — the evaluation pattern applied to this agent.

Patterns *not* yet applied in this example: governance posture, monitoring,
feedback loops. Those layer on later.

## Recipe to reproduce

1. **Init the v2 template** into your work area:

   ```bash
   databricks bundle init <path-to-agentops-stacks-v2> --config-file /tmp/init.json
   ```

   where `/tmp/init.json` contains:

   ```json
   {
     "input_project_name": "hello_agent",
     "input_root_dir": "hello-agent",
     "input_cloud": "azure",
     "input_cicd_platform": "github_actions"
   }
   ```

2. **Fill in workspace hosts** in `databricks.yml` (the `# TODO: set <env>
   workspace URL` placeholders).

3. **Add the agent and eval pattern files**: `src/hello_agent.py`,
   `notebooks/register_agent.py`, `evaluation/*` as shown in this directory.

## One-time setup

Before the CI eval gate can fire, the Hello Agent must be registered to UC:

1. Open `notebooks/register_agent.py` in your Databricks workspace (import
   it as a notebook via the workspace UI or the CLI).
2. Set the `catalog` widget to a UC catalog you have write access to (e.g.
   `hello_agent_dev`). The `schema` widget defaults to `hello_agent`.
3. Run all cells. The notebook registers the model and sets the `@champion`
   alias on the new version.

## Running the gate locally

```bash
uv sync
export DATABRICKS_CATALOG=<your-catalog>
export DATABRICKS_SCHEMA=<your-schema>
uv run python evaluation/gate.py
```

## What the gate enforces

See [`evaluation/README.md`](evaluation/README.md). Briefly: Safety
(blocking, 1.0) + Correctness (warning, 0.8) against 5 hand-written QAs.
