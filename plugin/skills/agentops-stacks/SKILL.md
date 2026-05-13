---
name: agentops-stacks
description: Scaffold a new AgentOps Stacks project — a Databricks Asset Bundle (DAB) with dev/staging/prod targets, Unity Catalog conventions, and CI/CD wiring for GitHub Actions, GitLab, or Azure DevOps across AWS, Azure, or GCP. Use when the user wants to start a new AI project on Databricks, generate a DAB scaffold, or set up CI/CD for an agent/ML project. Triggers on "scaffold a new agentops project", "new DAB with CI/CD", "start a new Databricks AI project", "create agentops-stacks project".
---

# agentops-stacks — Project Scaffold

## Overview

Generates the production envelope for an AI project on Databricks: DAB layout with dev/staging/prod targets, Unity Catalog schema and volume, MLflow experiment, and CI/CD workflows. Byte-identical to `databricks bundle init` output — the skill renders natively so it works in environments without the Databricks CLI and so behavior is identical across Claude Code, Cursor, and Genie Code.

Use this skill once per project, at the start. After scaffolding, the user develops their solution under `src/` and applies evaluation/governance/monitoring patterns separately as the project matures.

## Required inputs

Collect from the user before rendering. All four are required.

| Input | Type | Constraints | Notes |
|---|---|---|---|
| `project_name` | string | matches `^[a-z][a-z0-9_]{2,}$` | Used as bundle name, default catalog suffix, and root directory name. |
| `cloud` | enum | `aws`, `azure`, `gcp` | Determines CI/CD auth blocks. |
| `cicd_platform` | enum | `github_actions`, `github_actions_for_github_enterprise_servers`, `azure_devops`, `gitlab` | Selects which CI/CD directory ships. |
| `destination` | path | optional | Where to write. Defaults to `./<project_name>`. Pass `.` to populate the current directory. |

Ask the user each one. Defaults from `databricks_template_schema.json` are fine as suggestions, but always confirm. Don't guess — these decisions are load-bearing.

## How to run

The skill ships with a Python renderer (`render.py`) and a vendored copy of the template tree (`template/`).

### Quick path — invoke as a script

```bash
python3 SKILL_DIR/render.py \
  --project-name <name> \
  --cloud <aws|azure|gcp> \
  --cicd-platform <github_actions|github_actions_for_github_enterprise_servers|azure_devops|gitlab> \
  --destination <path>
```

`SKILL_DIR` is the directory this `SKILL.md` lives in. In Claude Code/Cursor it's typically `.claude/skills/agentops-stacks/`; in Genie Code it's `/Workspace/Users/<user>/.assistant/skills/agentops-stacks/`.

### Module path — call from Python

```python
import sys
sys.path.insert(0, "<SKILL_DIR>")
from render import scaffold

dest = scaffold(
    project_name="my_agent",
    cloud="aws",
    cicd_platform="github_actions",
    destination="./my_agent",
)
print(f"Scaffolded at {dest}")
```

The `scaffold(...)` function validates inputs, walks the template tree, and writes the rendered output. It refuses to scaffold over a non-empty destination (a `.git/` directory is allowed — for scaffolding into a fresh clone).

## Genie Code workspace flow

The typical flow:

1. User creates an empty repo in Databricks Repos via the workspace UI (e.g., `/Workspace/Repos/<user>/my-agent/`).
2. User opens Genie Code from that directory and asks to scaffold.
3. You collect the four inputs above, with `destination` set to `.` (the user is already inside the target).
4. Call `scaffold(...)` — files land at `/Workspace/Repos/<user>/my-agent/`.
5. The user commits and pushes through the Repos UI.

Git CLI is available in Genie Code, but repo lifecycle (create, commit, push) is currently more reliable through the workspace UI. Treat "repo exists in the workspace" as a prerequisite and instruct the user to set it up via the UI if they haven't.

## After scaffolding

Surface these next steps to the user, derived from the renderer's success message:

1. `cd <destination>`
2. Review `.agentops-stacks/manifest.yml` and `databricks.yml`
3. Set workspace hosts and Unity Catalog grants — see `docs/setup.md` in the rendered project
4. `uv sync` (generates `uv.lock` — must be committed)
5. `databricks bundle validate -t dev`

Do not attempt step 5 from within the skill — it requires the user's workspace authentication and is the first thing they'll exercise themselves.

## What this skill does NOT do

- Doesn't apply evaluation, governance, or monitoring patterns. Those are separate skills coming later.
- Doesn't create or clone git repos. The user owns repo creation.
- Doesn't deploy. The user runs `databricks bundle deploy` from their authenticated environment.
- Doesn't modify an existing scaffold. For retrofitting an existing project, a future `/adopt` workflow will handle that.

## Reference files

- `render.py` — the renderer + scaffold orchestrator
- `template/` — vendored copy of the canonical DAB template tree (installed alongside the skill)
- `databricks_template_schema.json` — input schema with defaults, validation patterns, and the success message

## Common issues

| Issue | Solution |
|---|---|
| `Invalid project_name`: must match the pattern | Pattern is `^[a-z][a-z0-9_]{2,}$`: starts with a lowercase letter, then lowercase letters/digits/underscores, min 3 chars. Reject `My-Project`, `1foo`, `ab`. |
| `Destination is not empty` | The destination has files besides `.git/`. Either pick an empty path or have the user move/remove the existing files. Do not silently overwrite. |
| `Template root not found` | The skill expects `template/` alongside `render.py`. If the installer didn't copy it, reinstall. |
| Renderer raises `Unsupported action` | The template uses Go-template syntax beyond the closed subset the renderer supports. This is a renderer bug — file an issue rather than working around it. |
