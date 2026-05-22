# agentops-stacks

A Databricks Asset Bundle (DAB) template + coding-assistant plugin for AI projects on Databricks. Scaffolds the production envelope — dev/staging/prod targets, Unity Catalog conventions, CI/CD wiring for four platforms — and adds production patterns (evaluation gates, governance posture, monitoring, feedback loops) as the project matures.

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

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) — recent enough to support the direct deployment engine (any release from the past 6 months is safe)
- [uv](https://docs.astral.sh/uv/) package manager
- A Databricks workspace with Unity Catalog enabled (one catalog per environment — see `docs/setup.md` in the rendered project)
- [ai-dev-kit plugin](https://github.com/databricks-solutions/ai-dev-kit) — required for the post-scaffold workflow (eval gates, monitoring, governance). Install before the plugin's post-scaffold skills land

---

## How to scaffold

There's one engine — `databricks bundle init` — and two ways to drive it.

### Run the CLI directly

Works anywhere `databricks` runs — local terminal, CI, or Genie Code.

```bash
databricks bundle init https://github.com/databricks-solutions/agentops-stacks
```

The CLI prompts for `project_name`, `cloud`, and `cicd_platform`. For non-interactive runs, supply the values via `--config-file <path>`:

```bash
cat > inputs.json <<'EOF'
{
  "input_project_name": "my_agent",
  "input_cloud": "aws",
  "input_cicd_platform": "github_actions"
}
EOF
databricks bundle init https://github.com/databricks-solutions/agentops-stacks --config-file inputs.json
```

### Drive the CLI from a coding assistant

The agentops-stacks plugin is a conversational UX layer over `bundle init`. It collects inputs through the assistant, writes the config file, runs the CLI, and surfaces the result. Use it when you want a guided scaffold and follow-up help from the assistant.

See [plugin/README.md](plugin/README.md) for install and usage. Two install flavors:

- **Genie Code install** — open `plugin/skills/install_genie_code_skills.py` as a notebook in your workspace and run all cells. The skill is then available in Genie Code.
- **Local install** — clone this repo, run `./plugin/skills/install_skills.sh` from your project root. The skill is then available in Claude Code or Cursor.

### Using the plugin

Once installed, the plugin is invoked by your coding assistant. There's nothing to call directly — describe what you want and the assistant runs the skill.

1. **Open your coding assistant** in the target directory:
   - **Genie Code** — pre-create the destination via the workspace UI (Workspace → Add → Git folder for a repo-backed project, or just create an empty folder under `/Workspace/Users/<you>/`), then open Genie Code from inside that directory.
   - **Claude Code / Cursor** — open the assistant in the directory where you want the scaffold to land.

2. **Ask the assistant to scaffold a project.** Either:
   - Type `/init-agentops-stacks` (Claude Code / Cursor only), or
   - Say "scaffold a new agentops-stacks project" — the assistant matches the skill's description and starts the flow.

3. **Answer the prompts.** The skill asks for project name, cloud (aws / azure / gcp), CI/CD platform, and destination. Defaults are sensible — confirm or adjust.

4. **Follow the next-steps message.** The CLI prints the post-scaffold sequence — `uv sync`, fill in `databricks.yml` workspace hosts, validate, deploy. The assistant relays it unchanged.

---

## After scaffolding

```bash
cd <project_name>
uv sync                                                       # generates uv.lock — commit it
databricks bundle validate -t dev --profile <dev-profile>
databricks bundle deploy -t dev --profile <dev-profile>
```

Set workspace hosts and Unity Catalog grants per `docs/setup.md` in the rendered project before deploying.

If the bundle was scaffolded inside a Databricks **Git folder** in the workspace (the recommended path for Genie Code users), the workspace UI also surfaces a **Deployments panel** on the bundle that lets you pick a target and deploy with one click — no terminal required. This matches the layout produced by the workspace UI's native "Create → Bundle" flow.

## Production patterns (TBD — plugin skills not yet built)

The CI/CD workflows already have hooks for the production patterns — for example, the prod-deploy workflow auto-detects `evaluation/thresholds.yml` and runs `evaluation/gate.py` if present — but the plugin skills that author the patterns aren't built yet.

Planned skills:

- **Eval gates** — `evaluation/thresholds.yml` + `evaluation/gate.py`. CI hook in place; authoring skill TBD.
- **Governance posture** — `governance/posture.md` + `governance/data_flows.md`. Prod-promotion check in place; authoring skill TBD.
- **Monitoring** — trace destination, alert rules, dashboards. Skill TBD.
- **Feedback loops** — end-user feedback UI, SME labeling, batch inference for offline eval. Skill TBD.
- **Adoption of existing projects** — `/adopt` workflow that detects what an existing project already has and adds only what's missing (manifest marker, CI/CD wiring, UC conventions). Skill TBD.

Until the skills ship, you can hand-roll any of these into a scaffolded project — the CI/CD hooks will pick them up.

## Documentation

- `template/{{.input_root_dir}}/README.md.tmpl` — what a rendered project looks like
- `template/{{.input_root_dir}}/AGENTS.md.tmpl` — conventions and guidance for coding agents
- `template/{{.input_root_dir}}/docs/setup.md.tmpl` — end-to-end configuration guide
- [Databricks Asset Bundles](https://docs.databricks.com/dev-tools/bundles/)
- [MLflow 3 + Unity Catalog](https://docs.databricks.com/mlflow3/)
