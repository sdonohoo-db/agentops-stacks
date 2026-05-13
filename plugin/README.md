# agentops-stacks plugin

A portable plugin that scaffolds AgentOps Stacks v2 projects from inside a coding assistant. Produces the same project shape as `databricks bundle init` on the canonical template — but works in environments where the Databricks CLI is unavailable (notably Genie Code).

The plugin and the [DAB template](../template/) share the same scaffold contract (`.agentops-stacks/manifest.yml`). The plugin is the additive on-ramp; the template stands on its own.

## What this plugin ships today

- One skill: **`agentops-stacks`** — scaffolds a new project (DAB layout, dev/staging/prod targets, UC schema and volume, MLflow experiment, CI/CD wiring for one of GitHub Actions, GitHub Actions for GHES, GitLab, or Azure DevOps).
- One command: **`/init-agentops-stacks`** — discoverability wrapper around the skill for Claude Code / Cursor users.
- Installers under `skills/` that mirror [ai-dev-kit's pattern](https://github.com/databricks-solutions/ai-dev-kit#installation).

Production patterns (evaluation gates, governance posture, monitoring, feedback loops) are not in this plugin yet. They land as separate skills as the project matures.

## How to install

### Local install (Claude Code, Cursor)

From your project root:

```bash
/path/to/agentops-stacks/plugin/skills/install_skills.sh
```

This creates `.claude/skills/agentops-stacks/` with the skill plus a bundled copy of the canonical template. The skill is self-contained — the renderer works without network access.

To also upload the skill to your Databricks workspace for Genie Code:

```bash
/path/to/agentops-stacks/plugin/skills/install_skills.sh --install-to-genie
/path/to/agentops-stacks/plugin/skills/install_skills.sh --install-to-genie --profile prod
```

This uploads to `/Workspace/Users/<you>/.assistant/skills/agentops-stacks/` using the named Databricks CLI profile.

### Genie Code install (no local clone needed)

Open `skills/install_genie_code_skills.py` as a notebook in your Databricks workspace and run all cells. It pulls the skill and bundled template from the repo and uploads to your `/Users/<you>/.assistant/skills/` path.

While v2 is staged on a personal fork, the notebook's `GITHUB_OWNER` / `GITHUB_REF` defaults point at it. Update those when v2 lands on `databricks-solutions/agentops-stacks` `main`.

## How to use

Once installed, either:

- Ask your coding assistant: "scaffold a new agentops project" (or similar). The assistant matches the skill description and runs it.
- In Claude Code or Cursor, type `/init-agentops-stacks`.

The skill will prompt for project name, cloud, CI/CD platform, and destination, then render the scaffold and print next-steps.

For the Genie Code workspace flow (create a Repos directory first, then scaffold into it with `.` as the destination), see the skill's `SKILL.md`.

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

At install time, the installer also bundles `template/`, `library/`, and `databricks_template_schema.json` from the repo root into the installed skill directory so the renderer has everything it needs in one place.

## Parity with `databricks bundle init`

The plugin's renderer covers a closed subset of Go-template syntax — exactly what the canonical template uses. Parity is verified by rendering the same inputs through `bundle init` and the plugin's renderer and diffing the output. All four cloud × CI/CD combinations currently produce byte-identical results.

If you extend the template with syntax the renderer doesn't yet support, the renderer will raise `SyntaxError: Unsupported action`. Either constrain the template change to the supported subset, or extend `render.py` deliberately (and add the new form to the parity matrix).
