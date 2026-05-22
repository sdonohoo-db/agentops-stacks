---
name: agentops-stacks
description: Scaffold a new AgentOps Stacks project — a Declarative Automation Bundle (DAB) with dev/staging/prod targets, Unity Catalog conventions, and CI/CD wiring for GitHub Actions, GitLab, or Azure DevOps across AWS, Azure, or GCP. Use when the user wants to start a new AI project on Databricks, generate a DAB scaffold, or set up CI/CD for an agent/ML project. Triggers on "scaffold a new agentops project", "new DAB with CI/CD", "start a new Databricks AI project", "create agentops-stacks project".
---

# agentops-stacks — Project Scaffold

## Overview

Generates the production envelope for an AI project on Databricks: DAB layout with dev/staging/prod targets, Unity Catalog schema and volume, MLflow experiment, and CI/CD workflows. The skill is a thin UX layer over `databricks bundle init` — it collects the four required inputs, writes them to a config file, and shells out to the CLI.

Use this skill once per project, at the start. After scaffolding, the user develops their solution under `src/` and applies evaluation, governance, and monitoring patterns from the ai-dev-kit plugin as the project matures.

## Prerequisites

This skill requires two things on every surface (Claude Code, Cursor, Genie Code):

1. **Databricks CLI.** Install from [docs.databricks.com](https://docs.databricks.com/dev-tools/cli/install.html). On local surfaces, run `databricks --version` to confirm; the CLI must be current enough to support the direct deployment engine (any release from the past 6 months is safe). Genie Code's wrapped CLI doesn't expose a version — trust the workspace and let `bundle init` errors surface if anything is wrong.
2. **ai-dev-kit plugin.** The post-scaffold workflow (eval gates, monitoring, governance) routes to ai-dev-kit skills like `databricks-bundles`, `databricks-mlflow-evaluation`, and `databricks-vector-search`. Install ai-dev-kit before guiding the user past the scaffold step.

If either is missing, surface the install instructions and stop. Do not attempt to work around an absent CLI or proceed past scaffold without ai-dev-kit available.

## Required inputs

Collect four inputs from the user before scaffolding. **Collect them one at a time, in the order below.** Do not present a summary table, multi-input form, or batch the questions in any way. Ask one question, wait for the answer, validate it, then move to the next. This pattern produces clearer audit trails than batch collection and mirrors deterministic-workflow tooling.

For each input:
1. State the input being collected and what it controls (one sentence).
2. Offer the default if applicable.
3. Wait for the user's response.
4. Validate against the constraints below.
5. If invalid, explain why and re-ask. If valid, acknowledge the value and move to the next input.

### 1. project_name (string)

- **Constraint:** matches `^[a-z][a-z0-9_]{2,}$` — starts with a lowercase letter; lowercase letters, digits, and underscores only; minimum 3 characters.
- **Used as:** bundle name, default catalog suffix, root directory name.
- **Reject and re-ask:** `My-Project`, `1foo`, `ab`, anything with hyphens or uppercase. Explain the pattern; don't just say "invalid."

### 2. cloud (enum)

- **Options:** `aws`, `azure`, `gcp`.
- **Default suggestion:** if you can infer the user's current workspace cloud, suggest matching it. Otherwise no default.
- **Determines:** CI/CD auth blocks in the rendered project.

### 3. cicd_platform (enum)

- **Options:** `github_actions`, `github_actions_for_github_enterprise_servers`, `azure_devops`, `gitlab`.
- **Determines:** which CI/CD directory ships in the scaffold.

### 4. destination (path, required to be a Git folder)

- **Default:** the current working directory if it is a Git folder; otherwise prompt.
- **Constraint:** the destination must be (or be inside) a Databricks Git folder. The CLI creates `<destination>/<project_name>/`. Don't ask the user to pre-create the project directory — `bundle init` handles that part.
- **Why a Git folder:** matches the layout produced by the Databricks workspace UI's "Create → Bundle" flow. When the scaffold lands inside a Git folder, the workspace UI surfaces a Deployments panel on the bundle that lets the user deploy to `dev` with one click — no CLI required. Scaffolding into a non-Git workspace folder still works for CLI-driven deploys but loses the UI Deployments path.
- **How to check:**
  - Claude Code / Cursor: `git rev-parse --show-toplevel` succeeds inside a Git folder, fails outside.
  - Genie Code: ask the user to confirm. The destination should be a folder they created via Workspace → Add → Git folder (or an existing such folder). If unsure, instruct them to create one via the workspace UI before continuing.
- **If the destination isn't a Git folder:** warn the user that the Workspace UI Deployments panel won't appear, offer to proceed anyway, and route them to CLI-only deploy in the next-steps message.

### Final confirmation

After all four inputs are collected, summarize back to the user once before running the CLI:

> "About to scaffold `<project_name>` for `<cloud>` + `<cicd_platform>` into `<destination>/<project_name>/`. Confirm?"

Only proceed on explicit confirmation. If the user wants to change any input, re-collect that single input — don't restart the whole sequence.

## How to run

1. **Verify the Databricks CLI.** On local surfaces (Claude Code, Cursor), run `databricks --version`. If it fails, surface the install instructions and stop. In Genie Code, skip this step — the wrapped CLI doesn't report a version cleanly; rely on `bundle init` errors instead.

2. **Write a temp config file** with the user's choices:
   ```json
   {
     "input_project_name": "<project_name>",
     "input_cloud": "<cloud>",
     "input_cicd_platform": "<cicd_platform>"
   }
   ```
   Save it to a tempfile under `/tmp/` (e.g., `/tmp/agentops-stacks-inputs.json`).

3. **Run `bundle init`** pointing at the agentops-stacks template:
   ```bash
   databricks bundle init https://github.com/databricks-solutions/agentops-stacks \
     --config-file <tempfile> \
     --output-dir <destination>
   ```
   The CLI clones the template repo, renders against the config, and writes the project to `<destination>/<project_name>/`.

   **Alternate template sources:**
   - Local clone: `databricks bundle init /path/to/agentops-stacks --config-file <tempfile> --output-dir <destination>` — faster, works offline.
   - Pinned branch or tag: add `--branch <name>` or `--tag <name>` to the git URL form.

4. **Leave the temp file in place.** It lives in `/tmp/` and the OS cleans it up. **Do not attempt to delete it programmatically** — Genie Code's safety heuristic blocks `os.remove`, `Path.unlink`, and equivalent file-deletion calls even for `/tmp` paths, which will surface a confusing "Code execution blocked" message at the end of a successful scaffold. The file is single-use; leaving it does no harm.

5. **Surface the CLI's stdout to the user.** `bundle init` prints the template's success message and next-steps verbatim — relay them unchanged. Do not re-summarize.

## Genie Code workspace flow

The canonical flow when running in Genie Code:

1. User creates an empty Git folder in the workspace via Workspace → Add → Git folder, pointing at an empty target repo (e.g., `/Workspace/Users/<user>/my-agent/`). This step is required — the scaffold must land inside a Git folder for the workspace UI Deployments panel to appear.
2. User opens Genie Code from inside that Git folder and asks to scaffold.
3. Collect the four inputs above. Set `destination` to the Git folder itself (the bundle will be created as `<git-folder>/<project_name>/` — matching the layout produced by Workspace UI's "Create → Bundle").
4. Run `databricks bundle init` with the git URL form (no local clone required in the workspace).
5. The scaffold lands at `<destination>/<project_name>/`. The user commits and pushes through the workspace UI's Git controls.
6. After scaffolding, the user can deploy via either the workspace UI's Deployments panel on the bundle (Targets → `dev` → Deploy) or the CLI (`databricks bundle deploy -t dev`).

Git CLI is available in Genie Code, but repo lifecycle (create, commit, push) is more reliable through the workspace UI. Treat "Git folder exists in the workspace" as a hard prerequisite and instruct the user to set it up via the UI if they haven't.

A Git folder can host multiple bundles as sibling subdirectories — the Workspace UI's Deployments pane is scoped per-bundle, not per-Git-folder. Re-running this skill against the same Git folder with a different `project_name` creates a coexisting bundle alongside the existing ones; each bundle gets its own Deployments pane and deploys independently.

## Scaffold-in-place limitation

`databricks bundle init` always creates `<destination>/<project_name>/`. There is no native flag to scaffold *into* an existing empty directory. If the user wants the scaffold contents at the root of an existing repo (instead of inside a subdirectory), scaffold to a temp location and `mv` the contents into place after. Don't attempt to outsmart the CLI with input_root_dir tricks — the path concatenation breaks in subtle ways.

## After scaffolding

Surface these next steps to the user, derived from the CLI's own success message:

1. `cd <destination>/<project_name>`
2. Review `.agentops-stacks/manifest.yml` and `databricks.yml`
3. Set workspace hosts and Unity Catalog grants — see `docs/setup.md` in the rendered project
4. `uv sync` (generates `uv.lock` — must be committed)
5. `databricks bundle validate -t dev`

**Two paths to deploy from here:**

- **Workspace UI (Genie Code default).** If the scaffold landed inside a Git folder, open the bundle in the workspace UI — the Deployments panel on the bundle view lets you pick a target (`dev`) and Deploy with one click. No terminal needed.
- **CLI.** `databricks bundle deploy -t dev` from the bundle's root directory. Works on every surface.

For the development work that follows (agent code, evaluation, monitoring), route to ai-dev-kit skills:
- `databricks-bundles` — bundle authoring, deployment, lifecycle
- `databricks-mlflow-evaluation` — MLflow 3 evaluation, scorers, judges
- `databricks-vector-search` — RAG, semantic search, similarity matching
- `databricks-app-python` — Databricks Apps in Python
- `databricks-genie` / `databricks-agent-bricks` — Genie Spaces, Knowledge Assistants, MAS

Do not attempt step 5 (`databricks bundle validate`) from within this skill — it requires the user's workspace authentication and is the first thing they'll exercise themselves.

## What this skill does NOT do

- Doesn't apply evaluation, governance, or monitoring patterns. Those are separate skills coming later in the agentops-stacks plugin.
- Doesn't create or clone git repos. The user owns repo creation.
- Doesn't deploy. The user runs `databricks bundle deploy` from their authenticated environment.
- Doesn't modify an existing scaffold. For retrofitting an existing project, a future `/adopt` workflow will handle that.

## Common issues

| Issue | Solution |
|---|---|
| `databricks: command not found` | Databricks CLI not installed. See [docs.databricks.com](https://docs.databricks.com/dev-tools/cli/install.html). |
| `Error: A new access token could not be retrieved...` | The CLI eagerly refreshes the default profile's token. Run `databricks auth login` to fix, or set `DATABRICKS_CONFIG_FILE` to an empty file for the scaffold call (auth is required for the next step anyway). |
| `Invalid project_name`: must match the pattern | Pattern is `^[a-z][a-z0-9_]{2,}$`: starts with a lowercase letter, then lowercase letters/digits/underscores, min 3 chars. Reject `My-Project`, `1foo`, `ab`. |
| Output directory not empty | `bundle init` refuses to overwrite. Pick an empty path or have the user move/remove existing files. |
| `Error: template path does not contain databricks_template_schema.json` | Wrong source path. The schema must be at the root of the template repo. Use the git URL form if the local-path resolution is uncertain. |
| Genie Code: `databricks --version` returns nothing | Expected — the Genie Code CLI wrapper doesn't expose `--version`. Skip the version check and proceed; surface `bundle init` errors if anything is wrong. |
| Workspace UI Deployments panel doesn't appear on the bundle | Bundle wasn't created inside a Git folder. The workspace UI only surfaces the Deployments panel for bundles under Git folders. Move the scaffold into a Git folder, or use the CLI to deploy (`databricks bundle deploy -t dev`). |

## Reference files

- `databricks_template_schema.json` (at the agentops-stacks repo root) — input schema with defaults, validation patterns, and the success message.
- `template/` (at the agentops-stacks repo root) — the canonical template tree the CLI renders against.
- Repo: <https://github.com/databricks-solutions/agentops-stacks>
