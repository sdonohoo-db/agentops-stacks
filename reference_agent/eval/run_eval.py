"""
Reference Agent Evaluation Runner
===================================
Runs automated evaluation for both the RAG agent and Summarization agent
using the eval dataset. Logs all results to MLflow.

This script is called by:
  - agent1_eval and agent2_eval tasks in the agent_development_workflow DAB job
  - CI validation tests in the staging environment
  - Developers locally during iteration

Usage:
    # Evaluate both agents (default)
    python reference_agent/eval/run_eval.py

    # Evaluate a specific agent
    python reference_agent/eval/run_eval.py --agent rag_agent
    python reference_agent/eval/run_eval.py --agent summarization_agent

    # Use a subset for fast iteration
    python reference_agent/eval/run_eval.py --sample 5

Exit codes:
    0 - All evaluations passed quality thresholds
    1 - One or more evaluations failed thresholds
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mlflow

from framework.config import get_config
from framework.evaluation.dataset import load_eval_dataset, sample_eval_dataset
from framework.evaluation.evaluator import AgentEvaluator, EvaluationThresholds
from framework.utils.mlflow_utils import setup_autologging

logger = logging.getLogger(__name__)

EVAL_DATASET_PATH = Path(__file__).parent / "eval_dataset.jsonl"


def run_rag_agent_eval(
    sample_size: int = 0,
    strict: bool = False,
) -> bool:
    """
    Evaluate the RAG agent on Q&A examples from the eval dataset.

    Args:
        sample_size: If > 0, sample this many rows for fast iteration.
        strict:      Use stricter thresholds (for staging → prod promotion).

    Returns:
        True if evaluation passed, False otherwise.
    """
    from reference_agent.agents.agent1.agent import RAGAgent

    cfg = get_config()
    setup_autologging(log_models=False)

    # Load and filter dataset to RAG-relevant samples
    df = load_eval_dataset(str(EVAL_DATASET_PATH))
    if "metadata" in df.columns:
        rag_df = df[df["metadata"].apply(
            lambda m: m.get("agent", "rag_agent") != "summarization_agent"
            if isinstance(m, dict) else True
        )]
    else:
        rag_df = df

    if sample_size > 0:
        rag_df = sample_eval_dataset(rag_df, n=sample_size)

    thresholds = EvaluationThresholds.strict() if strict else EvaluationThresholds()
    evaluator = AgentEvaluator(agent_name="rag_agent", thresholds=thresholds, config=cfg)

    logger.info("Evaluating RAG agent on %d samples...", len(rag_df))
    result = evaluator.run(
        agent=RAGAgent(config=cfg),
        eval_data=rag_df,
        run_name=f"rag_agent_eval_{cfg.env}",
    )

    print(result.summary())
    return result.passed()


def run_summarization_agent_eval(
    sample_size: int = 0,
    strict: bool = False,
) -> bool:
    """
    Evaluate the Summarization agent on summarization examples.

    Args:
        sample_size: If > 0, sample this many rows.
        strict:      Use stricter thresholds.

    Returns:
        True if evaluation passed, False otherwise.
    """
    from reference_agent.agents.agent2.agent import SummarizationAgent

    cfg = get_config()
    setup_autologging(log_models=False)

    # Load and filter to summarization samples
    df = load_eval_dataset(str(EVAL_DATASET_PATH))
    # Filter for summarization requests
    summ_df = df[df["request"].str.lower().str.startswith("summarize")]

    if sample_size > 0:
        summ_df = sample_eval_dataset(summ_df, n=sample_size)

    if len(summ_df) == 0:
        logger.warning("No summarization samples found in eval dataset.")
        return True

    thresholds = EvaluationThresholds.strict() if strict else EvaluationThresholds(
        correctness=0.7,  # Summarization is subjective — lower threshold
        groundedness=0.85,
        relevance=0.8,
        safety=1.0,
    )
    evaluator = AgentEvaluator(
        agent_name="summarization_agent",
        thresholds=thresholds,
        config=cfg,
    )

    logger.info("Evaluating Summarization agent on %d samples...", len(summ_df))
    result = evaluator.run(
        agent=SummarizationAgent(config=cfg),
        eval_data=summ_df,
        run_name=f"summarization_agent_eval_{cfg.env}",
    )

    print(result.summary())
    return result.passed()


def main(args: argparse.Namespace) -> int:
    """Main evaluation entry point. Returns exit code (0=pass, 1=fail)."""
    os.environ.setdefault("AGENTOPS_ENV", "dev")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    passed_all = True

    if args.agent in ("rag_agent", "all"):
        passed = run_rag_agent_eval(
            sample_size=args.sample,
            strict=args.strict,
        )
        if not passed:
            logger.error("RAG agent evaluation FAILED")
            passed_all = False
        else:
            logger.info("RAG agent evaluation PASSED")

    if args.agent in ("summarization_agent", "all"):
        passed = run_summarization_agent_eval(
            sample_size=args.sample,
            strict=args.strict,
        )
        if not passed:
            logger.error("Summarization agent evaluation FAILED")
            passed_all = False
        else:
            logger.info("Summarization agent evaluation PASSED")

    return 0 if passed_all else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AgentOps reference agent evaluation")
    parser.add_argument(
        "--agent",
        choices=["rag_agent", "summarization_agent", "all"],
        default="all",
        help="Which agent to evaluate (default: all)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Sample N rows for fast iteration (0 = use all)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Use stricter thresholds (for staging → prod gate)",
    )
    args = parser.parse_args()
    sys.exit(main(args))
