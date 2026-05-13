# agentops-stacks

A Databricks Asset Bundle (DAB) template + plugin for AI projects on Databricks. Scaffolds the production envelope — dev/staging/prod targets, Unity Catalog conventions, CI/CD wiring for four platforms — and adds production patterns (evaluation gates, governance posture, monitoring, feedback loops) as the project matures.

Currently published from the `sdonohoo-db/agentops-stacks` fork while in development. Will move to `databricks-solutions/agentops-stacks` once stabilized.

## What you get

agentops-stacks generates the production envelope for an AI project on Databricks. The scaffold includes:

- Three-environment Databricks Asset Bundle (dev / staging / prod) with `direct` deployment engine
- One Unity Catalog catalog per environment, plus a schema and managed volume for artifacts
- MLflow experiment configured to land artifacts in the volume
- CI/CD wiring for one of four platforms — GitHub Actions, GitHub Actions for GHES, GitLab, or Azure DevOps — with PR validation, staging deploy on merge to `main`, and prod deploy on `v*` tag
- Cloud auth (Azure service principal; AWS and GCP tokens) wired into the CI/CD workflows
- `AGENTS.md` with conventions for coding assistants
- `docs/setup.md` covering UC catalogs, CLI profiles, and CI/CD credentials

Application code, pipelines, model serving, jobs, and apps go under `src/` and new files in `resources/`. Familiarity with Databricks Asset Bundles and CI/CD pipelines is assumed.

## Prerequisites

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.295.0 or later
- [uv](https://docs.astral.sh/uv/) package manager
- A Databricks workspace with Unity Catalog enabled (one catalog per environment — see [docs/setup.md](template/{{.input_root_dir}}/docs/setup.md.tmpl))

---

## Two ways to scaffold

Both paths produce byte-identical project structure. Pick whichever fits your workflow.

### Path 1: Databricks CLI

Works anywhere `databricks` runs — local terminal, CI, or the Genie Code web terminal.

```bash
databricks bundle init https://github.com/sdonohoo-db/agentops-stacks
```

### Path 2: agentops-stacks plugin

Renders the same scaffold from inside a coding assistant — Claude Code, Cursor, or Genie Code — without leaving the assistant. Useful when you want a conversational scaffold and follow-up help.

See [plugin/README.md](plugin/README.md) for install and usage. Two install flavors:

- **Genie Code install** — open `plugin/skills/install_genie_code_skills.py` as a notebook in your workspace and run all cells. The skill is then available in Genie Code.
- **Local install** — clone this repo, run `./plugin/skills/install_skills.sh` from your project root. The skill is then available in Claude Code or Cursor.

---

## After scaffolding

Whichever path you took, the next steps are the same:

```bash
cd <project_name>
uv sync                                                       # generates uv.lock — commit it
databricks bundle validate -t dev --profile <dev-profile>
databricks bundle deploy -t dev --profile <dev-profile>
```

Set workspace hosts and Unity Catalog grants per [docs/setup.md](template/{{.input_root_dir}}/docs/setup.md.tmpl) before deploying.

## Production patterns (TBD — plugin skills not yet built)

The CI/CD workflows already have hooks for the production patterns — for example, the prod-deploy workflow auto-detects `evaluation/thresholds.yml` and runs `evaluation/gate.py` if present — but the plugin skills that author the patterns aren't built yet.

Planned (delivery sequence in [projectdocs/implementation-plan.md](projectdocs/implementation-plan.md)):

- **Eval gates** — `evaluation/thresholds.yml` + `evaluation/gate.py`. CI hook in place; authoring skill TBD.
- **Governance posture** — `governance/posture.md` + `governance/data_flows.md`. Prod-promotion check in place; authoring skill TBD.
- **Monitoring** — trace destination, alert rules, dashboards. Skill TBD.
- **Feedback loops** — end-user feedback UI, SME labeling, batch inference for offline eval. Skill TBD.

Until the skills ship, you can hand-roll any of these into a scaffolded project — the CI/CD hooks will pick them up.

## Status (v2)

v2 is a simplified, dual-channel rework:

- **DAB template** (this repo) — canonical scaffold. Generates the same project shape from any environment that runs `databricks bundle init`.
- **agentops-stacks plugin** (`plugin/`) — portable resident copilot for authoring projects from inside a coding assistant. Renders byte-identical output to `bundle init` across all four cloud × CI/CD combinations. Works in Claude Code, Cursor, and Genie Code.

Plugin and template share the same scaffold contract (`.agentops-stacks/manifest.yml`). The template stands on its own — the plugin is additive.

## Documentation

- `template/{{.input_root_dir}}/README.md.tmpl` — what a rendered project looks like
- `template/{{.input_root_dir}}/AGENTS.md.tmpl` — conventions and guidance for coding agents
- `template/{{.input_root_dir}}/docs/setup.md.tmpl` — end-to-end configuration guide
- [Databricks Asset Bundles](https://docs.databricks.com/dev-tools/bundles/)
- [MLflow 3 + Unity Catalog](https://docs.databricks.com/mlflow3/)
