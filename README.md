# agentops-stacks

A Databricks Asset Bundle (DAB) template that scaffolds production-ready AI projects on Databricks: dev/staging/prod targets, Unity Catalog conventions, CI/CD wiring for four platforms, and the hooks for evaluation, governance, and monitoring patterns. Build your solution under `src/` and apply production patterns as the project develops.

## Quick start

```bash
databricks bundle init https://github.com/sdonohoo-db/agentops-stacks --branch agentops-stacks-v2
```

You'll be prompted for project name, cloud, and CI/CD platform. After init:

```bash
cd <project_name>
uv sync
databricks bundle validate -t dev --profile <dev-profile>
databricks bundle deploy -t dev --profile <dev-profile>
```

v2 is staged on the `agentops-stacks-v2` branch of a personal fork while in development. The `--branch` flag drops once v2 lands on `databricks-solutions/agentops-stacks` main.

## Prerequisites

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.288.0 or later
- [uv](https://docs.astral.sh/uv/) package manager
- A Databricks workspace with Unity Catalog enabled (one catalog per environment — see `template/{{.input_root_dir}}/docs/setup.md.tmpl`)

## What's in the box

- **Bundle scaffold** — `databricks.yml` (direct deployment engine), `pyproject.toml`, dev/staging/prod targets with one catalog per environment.
- **Unity Catalog resources** — schema and managed volume for artifacts; MLflow experiment configured to land artifacts in the volume.
- **CI/CD workflows** — GitHub Actions, GitHub Actions for GitHub Enterprise Servers, GitLab, and Azure DevOps. PR validates; merge to `main` deploys to staging; tag `v*` deploys to prod.
- **Cloud auth** — Azure (service principal), AWS and GCP (token-based) wired into each CI/CD platform.
- **`AGENTS.md`** — tool-agnostic conventions for coding assistants (Claude Code, Cursor, Genie Code, GitHub Copilot, others).
- **`docs/setup.md`** — end-to-end configuration guide for UC catalogs, CLI profiles, and CI/CD credentials per cloud and platform.

The scaffold ships the structural pieces and nothing else. Application code, data prep pipelines, model serving, jobs, and apps are user additions under `src/` and new files in `resources/`.

## Production patterns

Evaluation, governance, and monitoring aren't pre-installed — they're applied as the solution develops:

- **Eval gates** — add `evaluation/thresholds.yml` and `evaluation/gate.py`; CI workflows auto-detect and gate promotion on them.
- **Governance posture** — add `governance/posture.md` and `governance/data_flows.md`; the prod-promotion workflow checks for presence.
- **Monitoring** — configure trace destination, alert rules, and dashboards per resource as you deploy them.

## Status (v2)

v2 is a simplified, dual-channel rework:

- **DAB template** (this repo) — canonical, pure-CLI scaffold. Generates the same project shape from any environment that runs `databricks bundle init`.
- **agentops-stacks Claude Code plugin** (planned) — resident copilot for authoring and adopting projects, applying production patterns interactively. Plugin and template share the same scaffold contract (`.agentops-stacks/manifest.yml`).

The template stands on its own — no plugin required.

## Documentation

- `template/{{.input_root_dir}}/README.md.tmpl` — what a rendered project looks like
- `template/{{.input_root_dir}}/AGENTS.md.tmpl` — conventions and guidance for coding agents
- `template/{{.input_root_dir}}/docs/setup.md.tmpl` — end-to-end configuration guide
- [Databricks Asset Bundles](https://docs.databricks.com/dev-tools/bundles/)
- [MLflow 3 + Unity Catalog](https://docs.databricks.com/mlflow3/)
