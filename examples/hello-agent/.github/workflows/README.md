# CI/CD — GitHub Actions

GitHub Actions workflows for validating and deploying **hello_agent** as a Databricks Asset Bundle.

## Workflows

| File | Trigger | What it does |
|------|---------|-------------|
| `hello_agent-bundle-ci.yml` | Pull request | Unit tests, bundle validate (staging), conditional eval gate |
| `hello_agent-bundle-cd-staging.yml` | Push to `main` | Validate + deploy to staging + post-deploy eval gate |
| `hello_agent-bundle-cd-prod.yml` | Tag matching `v*` | Validate + deploy to prod + eval gate + governance check |

## Setup

1. Create service principals for staging and prod workspaces and grant them the Unity Catalog permissions listed in the project README.
2. Add repository secrets:
   - **Azure:** `STAGING_AZURE_SP_TENANT_ID`, `STAGING_AZURE_SP_APPLICATION_ID`, `STAGING_AZURE_SP_CLIENT_SECRET` (and prod equivalents)
   - **AWS / GCP:** `STAGING_WORKSPACE_TOKEN`, `PROD_WORKSPACE_TOKEN`
3. Under Repo Settings → Actions → General → Workflow permissions, enable read + write so the eval-gate job can comment on PRs if you extend it to do so.

## Conditional jobs

The `eval_gate` and `governance_check` jobs use `hashFiles()` to detect the presence of `evaluation/thresholds.yml` and `governance/posture.md` respectively. They skip when those files aren't present — so the bare scaffold's pipelines run cleanly until you apply the eval and governance patterns.

For project-level setup details, see the [project README](../../README.md).
