# agentops-stacks plugin

A portable plugin that scaffolds AgentOps Stacks v2 projects from inside a coding assistant. Renders the same project shape as `databricks bundle init` against the canonical template, byte-for-byte. Works in Claude Code, Cursor, and Genie Code.

The plugin and the [DAB template](../template/) share the same scaffold contract (`.agentops-stacks/manifest.yml`). The plugin is the additive on-ramp; the template stands on its own.

## What this plugin ships today

- One skill: **`agentops-stacks`** — scaffolds a new project (DAB layout, dev/staging/prod targets, UC schema and volume, MLflow experiment, CI/CD wiring for one of GitHub Actions, GitHub Actions for GHES, GitLab, or Azure DevOps).
- One command: **`/init-agentops-stacks`** — discoverability wrapper around the skill for Claude Code / Cursor users.
- Installers under `skills/` that mirror [ai-dev-kit's pattern](https://github.com/databricks-solutions/ai-dev-kit#installation).

Production patterns (evaluation gates, governance posture, monitoring, feedback loops) are not in this plugin yet. They land as separate skills as the project matures.

## Try it — Genie Code

Prerequisites: a Databricks workspace, write access to your own `/Workspace/Users/<you>/` path.

1. In your workspace, open the file [`plugin/skills/install_genie_code_skills.py`](skills/install_genie_code_skills.py) as a notebook. The simplest way is to clone this repo as a Git folder in Workspace → Add → Git folder, then open the file.

2. Run all cells. The notebook pulls the latest skill and the bundled template from GitHub and uploads to `/Workspace/Users/<you>/.assistant/skills/agentops-stacks/`. The notebook defaults to `GITHUB_OWNER=sdonohoo-db` and `GITHUB_REF=main` — edit the configuration cell if you want a different fork or branch.

3. Pre-create the destination directory where you want the scaffold to land. For repo-backed projects, use the workspace UI: Workspace → Add → Git folder → paste the empty target repo URL → clone. For non-repo scratch projects, just create an empty folder under `/Workspace/Users/<you>/`.

4. Open Genie Code from inside that target directory and say "scaffold a new agentops-stacks project."

5. The skill will prompt for inputs and propose to run `render.py`. Genie Code shows a "Code execution blocked for safety reasons" prompt — this is expected (it triggers on the pattern of importing from `/Workspace` and creating files), not an error. Click **Run** to proceed; the scaffold lands in the destination you specified.

## Try it — Claude Code or Cursor

Prerequisites: `databricks` CLI installed (only required for `--install-to-genie`), a coding assistant that loads `.claude/skills/`.

1. Clone this repo somewhere local:
   ```bash
   git clone https://github.com/sdonohoo-db/agentops-stacks.git
   cd agentops-stacks
   ```

2. From your *target project's* root directory (or a fresh empty dir), run the installer pointing at the cloned repo:
   ```bash
   /path/to/agentops-stacks/plugin/skills/install_skills.sh
   ```
   The installer creates `.claude/skills/agentops-stacks/` in the current directory and copies the renderer plus the canonical template into it. The skill is then self-contained — no network needed for scaffolding.

3. Open Claude Code or Cursor in that directory and either:
   - Type `/init-agentops-stacks`, or
   - Say "scaffold a new agentops-stacks project."

   The assistant will prompt for project name, cloud, CI/CD platform, and destination, then render the scaffold.

## Combined: install locally and upload to Genie Code in one go

If you already have the repo cloned and want the skill in both places:

```bash
/path/to/agentops-stacks/plugin/skills/install_skills.sh --install-to-genie
/path/to/agentops-stacks/plugin/skills/install_skills.sh --install-to-genie --profile <profile-name>
```

This runs the local install, then uploads `.claude/skills/agentops-stacks/` to `/Workspace/Users/<you>/.assistant/skills/` using the named Databricks CLI profile (default: `DEFAULT` or `$DATABRICKS_CONFIG_PROFILE`).

## Layout

```
plugin/
├── README.md                                    # this file
├── commands/
│   └── init-agentops-stacks.md                  # CC/Cursor slash command
└── skills/
    ├── install_skills.sh                        # local + Genie upload installer
    ├── install_genie_code_skills.py             # in-workspace notebook installer
    └── agentops-stacks/
        ├── SKILL.md                             # skill instructions for the assistant
        └── render.py                            # native Go-template renderer + scaffold logic
```

At install time, the installer bundles `template/`, `library/`, and `databricks_template_schema.json` from the repo root into the installed skill directory so the renderer has everything it needs in one place.

## Parity with `databricks bundle init`

The plugin's renderer covers a closed subset of Go-template syntax — exactly what the canonical template uses. Parity is verified by rendering the same inputs through `bundle init` and the plugin's renderer and diffing the output. All four cloud × CI/CD combinations currently produce byte-identical results.

If you extend the template with syntax the renderer doesn't yet support, the renderer will raise `SyntaxError: Unsupported action`. Either constrain the template change to the supported subset, or extend `render.py` deliberately (and add the new form to the parity matrix).

## Known UX notes

- **Genie Code safety gate.** Each scaffold call surfaces a one-time "Code execution blocked for safety reasons" prompt because the skill imports a module from `/Workspace` and writes files. Click Run; the scaffold proceeds normally. This is a pattern-based heuristic, not a real safety issue.
- **Git workflow in Genie Code.** The git CLI is available in Genie Code, but repo lifecycle (create remote, commit, push) is currently more reliable through the workspace UI. The skill assumes you've set up the target repo / folder via the UI before scaffolding.
