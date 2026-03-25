---
name: read-manifest
description: Read and interpret the AgentOps deployment manifest
trigger: /read-manifest
category: operations
tags: [agentops, manifest, deployment, status]
---

Read and interpret `deployment_manifest.md` to understand what is deployed and its status.

## When to use
Use this skill when the user wants to:
- Check what is currently deployed
- Understand the status of a deployment
- Find endpoint URLs, job IDs, or MLflow experiment IDs
- Determine if deployment was successful

## What you should do

1. **Read the manifest** — read the file `deployment_manifest.md` in the project root.
   If it doesn't exist, tell the user no deployment has been recorded yet.

2. **Parse and present key information**:
   - Deployment status (SUCCESS / PARTIAL / FAILED)
   - Environment (dev / staging / prod)
   - Workspace URL
   - Deployed workflows (names, job IDs, URLs)
   - Model Serving endpoint (URL, state)
   - UC registered models
   - MLflow experiments

3. **Highlight any issues**:
   - Components with FAILED or PARTIAL status
   - Endpoints that are NOT_READY
   - Missing components

4. **Offer next actions**:
   - If status is PARTIAL or FAILED: suggest running `python scripts/verify.py`
   - If endpoint is not ready: suggest checking workspace logs
   - If no manifest: suggest running `python scripts/deploy.py --target dev`

5. **Also check verification_report.md** if it exists for detailed check results.

## Key files
- `deployment_manifest.md` — Primary deployment record
- `verification_report.md` — Detailed verification check results
- `scripts/verify.py` — Re-run verification
- `scripts/generate_manifest.py` — Regenerate manifest without redeploying
