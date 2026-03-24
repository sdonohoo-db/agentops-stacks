---
title: Evaluation
description: Automated agent quality gates using MLflow GenAI evaluation — configure judges, thresholds, and eval datasets
category: evaluation
tags: [evaluation, mlflow, genai, judges, quality-gates, correctness, groundedness]
related_docs: [agent-development.md, ci-cd.md, best-practices.md]
---

# Evaluation

Evaluation is the promotion gate. An agent cannot move to the next environment unless it passes all quality thresholds. This is enforced in CI and in the agent development DAB workflow.

---

## Evaluation Stack

| Component | Location |
|---|---|
| `AgentEvaluator` | `framework/evaluation/evaluator.py` |
| `EvaluationThresholds` | `framework/evaluation/evaluator.py` |
| `load_eval_dataset()` | `framework/evaluation/dataset.py` |
| `DatabricksJudge` (custom) | `framework/evaluation/metrics.py` |
| Reference eval runner | `reference_agent/eval/run_eval.py` |
| Reference eval dataset | `reference_agent/eval/eval_dataset.jsonl` — 75 labelled samples across 15 categories |

---

## Quick Start

```python
from framework.evaluation.evaluator import AgentEvaluator
from reference_agent.agents.agent1.agent import RAGAgent

agent = RAGAgent()
evaluator = AgentEvaluator(agent_name="rag_agent")

result = evaluator.run(
    agent=agent,
    eval_data="reference_agent/eval/eval_dataset.jsonl",
)

print(result.summary())
# correctness:   0.87 ✓
# groundedness:  0.93 ✓
# relevance:     0.79 ✓
# safety:        0.98 ✓
# PASSED

assert result.passed(), "Evaluation failed — check MLflow for trace details"
```

---

## Eval Dataset Format

Datasets are JSONL files with one JSON object per line.

**Minimum required field:** `request`

**Recommended fields:**

```jsonl
{"request": "What is the refund policy?", "expected_response": "Refunds are accepted within 30 days of purchase.", "retrieved_context": "Section 4.2: Refund Policy..."}
{"request": "Summarize the onboarding document", "expected_response": "The onboarding doc covers IT setup, HR forms, and team introductions."}
```

| Field | Required | Purpose |
|---|---|---|
| `request` | Yes | User input sent to the agent |
| `expected_response` | Recommended | Ground truth for correctness judge |
| `retrieved_context` | Optional | Expected retrieval for groundedness judge |
| `metadata` | Optional | Tags for grouping results in MLflow |

### Loading datasets

```python
from framework.evaluation.dataset import load_eval_dataset

# From JSONL file
df = load_eval_dataset("reference_agent/eval/eval_dataset.jsonl")

# From a list of dicts
df = load_eval_dataset([
    {"request": "What is X?", "expected_response": "X is Y."},
])

# From a Delta table
df = load_eval_dataset("agentops_dev.agentops.eval_dataset_rag_v1", spark=spark)

# From an existing DataFrame (passthrough)
df = load_eval_dataset(existing_df)
```

---

## Scorers

AgentOps uses MLflow's built-in GenAI scorers (`mlflow.genai.scorers`):

| Scorer | Measures | Default Threshold |
|---|---|---|
| `Correctness` | Does the response match the expected answer? | 0.80 |
| `RetrievalGroundedness` | Is the response grounded in retrieved context? | 0.90 |
| `RelevanceToQuery` | Does the response address the user's question? | 0.80 |
| `Safety` | Is the response free of harmful content? | 1.00 |

These are defined in `EvaluationThresholds`:

```python
from framework.evaluation.evaluator import EvaluationThresholds

# Default thresholds
thresholds = EvaluationThresholds()

# Stricter thresholds for staging → prod gate
thresholds = EvaluationThresholds(
    correctness=0.85,
    groundedness=0.92,
    relevance=0.80,
    safety=0.97,
)
```

### Custom scorer

For domain-specific evaluation (e.g., "is the response compliant with legal requirements?"):

```python
from mlflow.genai.scorers import Guidelines

legal_compliance_scorer = Guidelines(
    name="legal_compliance",
    guidelines="Evaluate whether the response is consistent with legal and regulatory requirements.",
)

evaluator = AgentEvaluator(
    agent_name="policy_agent",
    extra_scorers=[legal_compliance_scorer],
)
```

---

## Running Evaluation

### From CLI (reference agent)

```bash
# Full eval on all agents
python reference_agent/eval/run_eval.py

# Quick sample (dev iteration)
python reference_agent/eval/run_eval.py --sample 5

# Specific agent only
python reference_agent/eval/run_eval.py --agent rag_agent

# Strict mode (staging → prod gate)
python reference_agent/eval/run_eval.py --strict
```

### From Python

```python
from reference_agent.eval.run_eval import run_all_evals

results = run_all_evals(sample_size=10, strict=False)
for agent_name, result in results.items():
    print(f"{agent_name}: {'PASSED' if result.passed() else 'FAILED'}")
```

---

## MLflow Integration

Every evaluation run is logged to MLflow automatically. The `AgentEvaluator` calls `mlflow.genai.evaluate()` which:

1. Invokes the agent on every eval row
2. Runs all judges on each response
3. Logs per-row scores and aggregate metrics to the MLflow experiment
4. Produces traces for every agent invocation

### Viewing results

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
# Open http://localhost:5000 → Experiments → agentops_{env}
```

In the MLflow UI, look for:
- **Metrics tab**: aggregate scores per judge
- **Traces tab**: per-invocation traces with input, output, retrieved context, and scores
- **Artifacts tab**: per-row CSV with individual scores

### Experiment naming convention

```
agentops_dev       # dev evaluation runs
agentops_staging   # staging (CI) evaluation runs
agentops_prod      # prod evaluation runs (monitoring)
```

---

## Saving Eval Datasets to Delta

For long-term tracking and reuse across environments:

```python
from framework.evaluation.dataset import save_eval_dataset_to_delta

table = save_eval_dataset_to_delta(
    df=eval_df,
    dataset_name="rag_agent_v2",
)
print(f"Saved to {table}")
# agentops_dev.agentops.eval_dataset_rag_agent_v2
```

Datasets saved to Delta are versioned via Delta's time travel and auditable via Unity Catalog lineage.

---

## Evaluation in the Promotion Pipeline

```
dev branch:
  agent_development_workflow (DAB) runs eval
      → agent1_eval: correctness ≥ 0.80 AND groundedness ≥ 0.90
      → agent2_eval: correctness ≥ 0.80
      → FAIL blocks the job, prevents model registration

PR to main (staging CI):
  GitHub Actions runs full eval with --strict thresholds
      → Must pass before merge

release branch:
  CD pipeline runs verify.py which calls evaluate on a smoke dataset
      → test inference must succeed
```

Eval failures are surfaced in GitHub PR comments with a direct link to the MLflow experiment run.
