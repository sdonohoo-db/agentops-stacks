---
description: Scaffold a new AgentOps Stacks project (DAB + CI/CD).
---

Use the `agentops-stacks` skill to scaffold a new project.

1. Collect required inputs from the user: `project_name`, `cloud`, `cicd_platform`, and `destination` (the parent directory; the CLI creates `<destination>/<project_name>/`).
2. Verify prerequisites (Databricks CLI on local surfaces, ai-dev-kit plugin for post-scaffold work).
3. Run `databricks bundle init` against the agentops-stacks template repo with the user's inputs supplied via `--config-file`.
4. Surface the CLI's next-steps message unchanged.

Defer to the skill's SKILL.md for full details — including the Genie Code workspace flow, input constraints, version handling, and what the skill does NOT do.
