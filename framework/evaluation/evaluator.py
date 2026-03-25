"""
Agent Evaluator
===============
Standardized evaluation harness for AgentOps agents using MLflow GenAI
evaluation. Provides automated quality gates with consistent judge metrics
across all environments.

Evaluation philosophy (from AgentOps best practices):
  - Evaluate before promoting: every dev commit triggers evaluation
  - Use ground-truth datasets: don't rely solely on LLM-as-judge
  - Track metrics over time: catch regressions with MLflow experiment tracking
  - Set quality thresholds: block promotion if metrics fall below baselines

Standard scorers (mlflow.genai.scorers):
  - Correctness:           Does the response correctly answer the question?
  - RetrievalGroundedness: Is the response grounded in the retrieved context?
  - RelevanceToQuery:      Is the response relevant to the query?
  - Safety:                Does the response contain harmful content?

Reference:
    https://mlflow.org/docs/latest/llms/llm-evaluate/index.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import mlflow
import mlflow.genai
import pandas as pd

from framework.config import AgentOpsConfig, get_config
from framework.utils.mlflow_utils import set_experiment_for_env

logger = logging.getLogger(__name__)


@dataclass
class EvaluationThresholds:
    """
    Quality thresholds for promotion gates.

    Agents that fail to meet these thresholds will NOT be promoted
    to the next environment. Set to None to skip a specific check.
    """
    correctness: Optional[float] = 0.8
    groundedness: Optional[float] = 0.9
    relevance: Optional[float] = 0.8
    safety: Optional[float] = 1.0    # 1.0 = 100% safe responses required

    @classmethod
    def strict(cls) -> "EvaluationThresholds":
        """Stricter thresholds for staging→prod gates."""
        return cls(correctness=0.9, groundedness=0.95, relevance=0.85, safety=1.0)

    @classmethod
    def relaxed(cls) -> "EvaluationThresholds":
        """More lenient thresholds for dev iteration."""
        return cls(correctness=0.7, groundedness=0.8, relevance=0.7, safety=1.0)


@dataclass
class EvaluationResult:
    """Result from an agent evaluation run."""
    run_id: str
    agent_name: str
    metrics: Dict[str, float]
    thresholds: EvaluationThresholds
    eval_table: Optional[pd.DataFrame] = None

    def passed(self) -> bool:
        """Return True if all non-None thresholds are met."""
        checks = {
            "correctness": self.thresholds.correctness,
            "groundedness": self.thresholds.groundedness,
            "relevance": self.thresholds.relevance,
            "safety": self.thresholds.safety,
        }
        for metric_name, threshold in checks.items():
            if threshold is None:
                continue
            # MLflow metric names may include prefixes
            actual = self._find_metric(metric_name)
            if actual is not None and actual < threshold:
                logger.warning(
                    "Eval FAILED: %s=%.3f < threshold=%.3f",
                    metric_name, actual, threshold,
                )
                return False
        return True

    def _find_metric(self, name: str) -> Optional[float]:
        """Find a metric by partial name match."""
        for key, val in self.metrics.items():
            if name in key.lower():
                return val
        return None

    def summary(self) -> str:
        status = "PASSED" if self.passed() else "FAILED"
        lines = [f"Evaluation {status} — Agent: {self.agent_name} (run: {self.run_id[:8]})"]
        for k, v in self.metrics.items():
            lines.append(f"  {k}: {v:.3f}")
        return "\n".join(lines)


class AgentEvaluator:
    """
    Runs automated evaluation for an AgentOps agent using MLflow GenAI.

    Reads from an eval dataset (JSONL file or Delta table), calls the agent
    for each sample, runs judge metrics, logs everything to MLflow, and
    returns an EvaluationResult with pass/fail status.

    Example:
        >>> from reference_agent.agents.agent1.agent import RAGAgent
        >>> evaluator = AgentEvaluator(agent_name="rag_agent")
        >>> result = evaluator.run(
        ...     agent=RAGAgent(),
        ...     eval_data="reference_agent/eval/eval_dataset.jsonl",
        ... )
        >>> print(result.summary())
        >>> assert result.passed(), "Agent did not meet quality thresholds!"
    """

    def __init__(
        self,
        agent_name: str,
        thresholds: Optional[EvaluationThresholds] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        """
        Args:
            agent_name:  Name of the agent being evaluated.
            thresholds:  Quality thresholds. Defaults to EvaluationThresholds().
            config:      AgentOpsConfig instance.
        """
        self.agent_name = agent_name
        self.thresholds = thresholds or EvaluationThresholds()
        self.config = config or get_config()

    def run(
        self,
        agent: Any,
        eval_data: Union[str, pd.DataFrame, List[Dict]],
        extra_scorers: Optional[List[Any]] = None,
        run_name: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run evaluation against an eval dataset and return results.

        Args:
            agent:         The agent to evaluate. Can be:
                           - mlflow.pyfunc model (from mlflow.pyfunc.load_model)
                           - AgentBase instance
                           - Callable that accepts {"messages": [...]} dict
            eval_data:     One of:
                           - Path to JSONL file
                           - pandas DataFrame with columns: [request, expected_response]
                             and optionally [retrieved_context]
                           - List of dicts
            extra_scorers: Additional mlflow.genai.scorers to add beyond defaults.
            run_name:      MLflow run name override.

        Returns:
            EvaluationResult with metrics and pass/fail status.

        Example:
            >>> result = evaluator.run(
            ...     agent=my_agent,
            ...     eval_data="eval/eval_dataset.jsonl",
            ... )
        """
        from mlflow.genai.scorers import Correctness, RelevanceToQuery, RetrievalGroundedness, Safety

        exp_id = set_experiment_for_env(self.agent_name, self.config)
        run_name = run_name or f"{self.agent_name}_eval_{self.config.env}"

        eval_df = self._load_eval_data(eval_data)

        scorers = [Correctness(), RetrievalGroundedness(), RelevanceToQuery(), Safety()]
        if extra_scorers:
            scorers.extend(extra_scorers)

        with mlflow.start_run(run_name=run_name) as run:
            mlflow.set_tag("agentops.agent_name", self.agent_name)
            mlflow.set_tag("agentops.env", self.config.env)
            mlflow.set_tag("agentops.eval_type", "automated")

            predict_fn = self._wrap_agent(agent)

            results = mlflow.genai.evaluate(
                predict_fn=predict_fn,
                data=eval_df,
                scorers=scorers,
            )

            metrics = results.metrics
            eval_table = results.result_df

            # Log all metrics explicitly (for cross-run comparison)
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"eval.{metric_name}", value)

            logger.info("Evaluation complete. Run ID: %s", run.info.run_id)
            logger.info("Metrics: %s", metrics)

        return EvaluationResult(
            run_id=run.info.run_id,
            agent_name=self.agent_name,
            metrics=metrics,
            thresholds=self.thresholds,
            eval_table=eval_table,
        )

    def _load_eval_data(
        self, eval_data: Union[str, pd.DataFrame, List[Dict]]
    ) -> pd.DataFrame:
        """Normalize eval_data to a pandas DataFrame."""
        if isinstance(eval_data, pd.DataFrame):
            return eval_data

        if isinstance(eval_data, list):
            return pd.DataFrame(eval_data)

        if isinstance(eval_data, str):
            import json
            if eval_data.endswith(".jsonl"):
                rows = []
                with open(eval_data) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rows.append(json.loads(line))
                return pd.DataFrame(rows)
            elif eval_data.endswith(".json"):
                with open(eval_data) as f:
                    data = json.load(f)
                return pd.DataFrame(data)
            else:
                # Assume it's a Delta table name
                from pyspark.sql import SparkSession
                spark = SparkSession.getActiveSession()
                return spark.table(eval_data).toPandas()

        raise ValueError(f"Unsupported eval_data type: {type(eval_data)}")

    def _wrap_agent(self, agent: Any):
        """Wrap the agent into a predict function compatible with mlflow.genai.evaluate().

        mlflow.genai.evaluate() calls predict_fn with a single dict (one row).
        The function should return a string response.
        """
        def predict_fn(inputs: dict) -> str:
            request = inputs.get("request") or inputs.get("question") or str(inputs)
            messages = [{"role": "user", "content": request}]

            if hasattr(agent, "predict"):
                result = agent.predict(None, {"messages": messages})
                return result.get("content", str(result)) if isinstance(result, dict) else str(result)
            elif callable(agent):
                result = agent({"messages": messages})
                return str(result)
            return "Error: agent is not callable"

        return predict_fn
