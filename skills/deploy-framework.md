---
name: deploy-agentops
description: Deploy the AgentOps framework to a Databricks workspace
trigger: /deploy-agentops
category: deployment
tags: [agentops, databricks, deploy, dag]
---

Deploy the AgentOps framework to a Databricks workspace using Databricks Asset Bundles.

## When to use
Use this skill when the user wants to:
- Deploy AgentOps to a dev, staging, or production workspace
- Validate the bundle configuration
- Trigger a specific AgentOps workflow after deployment

## What you should do

1. **Determine the target environment** — ask the user if not specified: dev, staging, or prod
2. **Check prerequisites**:
   - Verify `databricks` CLI is installed: `databricks --version`
   - Verify workspace connectivity: `databricks workspace ls /`
   - Confirm Unity Catalog catalogs exist (or offer to create them)
3. **Validate the bundle** before deploying:
   ```bash
   databricks bundle validate --target <target>
   ```
4. **Deploy**:
   ```bash
   python scripts/deploy.py --target <target>
   ```
   Or directly via CLI:
   ```bash
   databricks bundle deploy --target <target>
   ```
5. **After deployment**, always:
   - Generate the manifest: `python scripts/generate_manifest.py --target <target>`
   - Run verification: `python scripts/verify.py --target <target>`
   - Show the user the key results from `deployment_manifest.md`

## Key files
- `scripts/deploy.py` — Full deployment script with validation and manifest
- `databricks.yml` — Root bundle configuration (project root)
- `bundle/targets/` — Per-environment variable overrides
- `deployment_manifest.md` — Generated post-deployment

## Common issues
- **"Workspace not found"**: Run `databricks configure` to set up credentials
- **"Catalog does not exist"**: Create Unity Catalog catalogs first (see docs/deployment.md)
- **"Bundle validation failed"**: Check databricks.yml syntax with `databricks bundle validate`
