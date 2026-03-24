---
name: run-eval
description: Run the automated evaluation suite for AgentOps agents
trigger: /run-eval
category: evaluation
tags: [agentops, evaluation, mlflow, quality]
---

Run automated evaluation for AgentOps agents and surface results from MLflow.

## When to use
Use this skill when the user wants to:
- Run evaluation before committing to check quality
- Check if evaluation thresholds are met
- View eval results and understand pass/fail reasons
- Run a quick sample evaluation during development

## What you should do

1. **Determine what to evaluate** — ask if not clear:
   - Which agent? (rag_agent, summarization_agent, or all)
   - Full dataset or sample? (sample is faster for dev iteration)

2. **Run the evaluation**:
   ```bash
   # Evaluate all agents
   python reference_agent/eval/run_eval.py

   # Evaluate specific agent
   python reference_agent/eval/run_eval.py --agent rag_agent

   # Quick sample (5 examples, for dev iteration)
   python reference_agent/eval/run_eval.py --sample 5

   # Strict mode (staging → prod gate thresholds)
   python reference_agent/eval/run_eval.py --strict
   ```

3. **Interpret results**:
   - Exit code 0 = PASSED (all thresholds met)
   - Exit code 1 = FAILED (one or more thresholds not met)
   - Check the printed summary for per-metric scores

4. **View in MLflow** — provide the MLflow experiment URL:
   - Dev: `<workspace_url>/#mlflow/experiments`
   - Experiment name: `/AgentOps/dev/<agent_name>`

5. **If evaluation fails**, help diagnose:
   - Low `correctness`: Check system prompt and RAG retrieval quality
   - Low `groundedness`: Agent may be hallucinating — check retrieved context
   - Low `relevance`: Check if the question is within the agent's scope
   - Safety failure: Review agent output for policy violations

## Quality Thresholds (default)
| Metric | Dev Threshold | Staging Threshold |
|---|---|---|
| correctness | 0.80 | 0.90 |
| groundedness | 0.90 | 0.95 |
| relevance | 0.80 | 0.85 |
| safety | 1.00 | 1.00 |

## Key files
- `reference_agent/eval/run_eval.py` — Evaluation runner
- `reference_agent/eval/eval_dataset.jsonl` — Eval dataset
- `framework/evaluation/evaluator.py` — AgentEvaluator class
- `framework/evaluation/metrics.py` — Custom judge metrics
