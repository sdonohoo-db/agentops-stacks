---
title: CI/CD Pipelines
description: GitHub Actions CI/CD for automated testing, quality gates, and production deployment via Databricks Asset Bundles
category: ci-cd
tags: [ci-cd, github-actions, databricks-asset-bundles, testing, deployment, automation]
related_docs: [evaluation.md, deployment.md, architecture.md]
---

# CI/CD Pipelines

AgentOps uses two GitHub Actions workflows to automate the test-evaluate-deploy cycle. The branch model maps directly to environments: `dev` → `main` → `release` corresponds to dev → staging → prod.

---

## Branch Model

```
dev branch     →  CI runs: bundle validate + unit tests + integration tests + validation tests
                   │
                   └──► PR to main: same CI gates must pass
                                │
                               main branch (staging)
                                │
                               PR to release: manual review
                                │
                            release branch  →  CD runs: bundle deploy prod + manifest + verify
```

---

## CI Pipeline (`ci.yml`)

**File:** `.github/workflows/ci.yml`
**Triggers:** Push to `dev`, pull requests targeting `main`

### Jobs (run in sequence)

```
validate-bundle  (no Databricks auth required)
      ↓
unit-tests       (no Databricks auth required)
      ↓
integration-tests  (requires DATABRICKS_STAGING_HOST + DATABRICKS_STAGING_TOKEN)
      ↓
validation-tests   (agent quality gate — mlflow.genai.evaluate())
      ↓
PR comment with MLflow experiment link
```

### Job 1: Bundle Validation

Two steps: (1) build the Python wheel (`pip install build && python -m build`) — required because bundle validation checks that the wheel artifact referenced by all `python_wheel_task` entries can be resolved; (2) run `databricks bundle validate --target dev`. Catches YAML syntax errors, missing variable references, and missing wheel artifacts before any Databricks connection is needed.

> **Note on CI secrets in `if` conditions**: Job-level `if` expressions cannot read `secrets.*` values directly — GitHub Actions always treats them as empty. Integration and validation test jobs gate on `env.DATABRICKS_HOST != ''` where the env var is set from the secret at workflow level. This is the correct pattern; do not change it to reference `secrets.*` directly.

### Job 2: Unit Tests

Runs `pytest tests/unit/` — no Databricks credentials required. Tests framework logic (router dispatch, chunking, metric calculations) using mocks.

```bash
pytest tests/unit/ -v --cov=framework --cov-report=xml
```

### Job 3: Integration Tests

Requires `DATABRICKS_STAGING_HOST` and `DATABRICKS_STAGING_TOKEN` secrets. Tests against the live staging workspace:
- Vector Search index read
- UC function invocation
- MLflow trace write/read

Skipped automatically if staging secrets are not configured.

### Job 4: Validation Tests

Runs `mlflow.genai.evaluate()` against the reference agent on a sample of the eval dataset. Asserts:
- `correctness >= 0.80`
- `groundedness >= 0.90`

Uses `EVAL_SAMPLE_SIZE=10` for CI speed. Full dataset runs in the DAB workflow.

On completion (pass or fail), posts a comment to the PR with a table of results and a link to the MLflow experiment:

```
## AgentOps CI Results
| Test Tier | Status |
|---|---|
| Unit Tests | ✅ PASSED |
| Integration Tests | ✅ PASSED |
| Validation Tests | ✅ PASSED |
[View MLflow Experiments](https://staging.workspace/mlflow/experiments)
```

---

## CD Pipeline (`cd.yml`)

**File:** `.github/workflows/cd.yml`
**Triggers:** Push to `release` branch
**Requires:** GitHub Environment `production` (manual approval gate)

### Steps

1. **Bundle validate** (`databricks bundle validate --target prod`) — Confirm prod target config is valid
2. **Bundle deploy** (`databricks bundle deploy --target prod`) — Deploy all workflows to prod workspace
3. **Generate manifest** (`python scripts/generate_manifest.py --target prod`) — Write `deployment_manifest.md`
4. **Verify** (`python scripts/verify.py --target prod --test-inference`) — Live health check
5. **Commit manifest** — Commits `deployment_manifest.md` + `verification_report.md` to the release branch
6. **Create GitHub summary** — Posts deployment summary to the workflow run page

If any step fails, a GitHub Issue is automatically created with label `deployment production urgent` and a link to the failed run.

---

## Required Secrets

Configure these in GitHub → Settings → Secrets and Variables → Actions:

| Secret | Description |
|---|---|
| `DATABRICKS_DEV_HOST` | Dev workspace URL (`https://...azuredatabricks.net`) |
| `DATABRICKS_DEV_TOKEN` | Dev workspace PAT or service principal token |
| `DATABRICKS_STAGING_HOST` | Staging workspace URL |
| `DATABRICKS_STAGING_TOKEN` | Staging workspace token |
| `DATABRICKS_PROD_HOST` | Prod workspace URL |
| `DATABRICKS_PROD_TOKEN` | Prod workspace token |

**Optional variables** (fall back to defaults if not set):

| Variable | Default |
|---|---|
| `AGENTOPS_DEV_CATALOG` | `agentops_dev` |
| `AGENTOPS_PROD_CATALOG` | `agentops_prod` |

---

## GitHub Environments

The CD workflow uses a GitHub Environment named `production`. This enables:
- **Manual approval gate** — a designated reviewer must approve before deploy starts
- **Environment-scoped secrets** — prod tokens can be scoped to the production environment only
- **Deployment history** — GitHub tracks every prod deployment with actor and timestamp

To configure: GitHub repo → Settings → Environments → New environment → `production` → Required reviewers.

---

## Test Tiers Summary

| Tier | Location | Needs Databricks | When |
|---|---|---|---|
| Unit | `tests/unit/` | No | Every push, every PR |
| Integration | `tests/integration/` | Yes (staging) | After unit tests pass |
| Validation | `tests/validation/` | Yes (staging) | After integration tests pass |

### Adding tests to a tier

**Unit**: Pure Python only. No Databricks imports. Use `unittest.mock` for all external dependencies.

```python
# tests/unit/test_my_agent.py
def test_my_agent_returns_string():
    agent = MyAgent(config=make_test_config())
    result = agent._invoke([{"role": "user", "content": "test"}])
    assert isinstance(result, str)
```

**Integration**: Use real Databricks credentials. Mark with `@pytest.mark.integration` if you want selective runs.

```python
# tests/integration/test_vector_search.py
def test_vs_index_queryable(vs_client):
    results = vs_client.get_index("agentops_dev.agentops.agentops_vs_index").similarity_search(
        query_text="refund policy",
        columns=["content"],
        num_results=3,
    )
    assert len(results.get_dict()["result"]["data_array"]) == 3
```

**Validation**: Use `AgentEvaluator` with real eval dataset and live agent.

```python
# tests/validation/test_agent_quality.py
def test_rag_agent_quality(agent, eval_dataset_path):
    evaluator = AgentEvaluator(agent_name="rag_agent")
    result = evaluator.run(agent=agent, eval_data=eval_dataset_path)
    assert result.passed(), result.summary()
```

---

## Running CI Locally

Simulate the CI pipeline locally before pushing:

```bash
# Step 1: Bundle validation
databricks bundle validate --target dev

# Step 2: Unit tests
pytest tests/unit/ -v

# Step 3: Integration tests (requires DATABRICKS_HOST + DATABRICKS_TOKEN)
AGENTOPS_ENV=staging pytest tests/integration/ -v

# Step 4: Validation tests (quick sample)
AGENTOPS_ENV=staging EVAL_SAMPLE_SIZE=5 pytest tests/validation/ -v
```

---

## Skipping CI on Trivial Changes

Add `[skip ci]` to your commit message to skip CI on documentation-only changes:

```bash
git commit -m "docs: update README [skip ci]"
```

Note: The CD pipeline cannot be skipped — every push to `release` triggers deployment.
