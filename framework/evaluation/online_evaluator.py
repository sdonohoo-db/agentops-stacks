"""
Online Evaluator
================
Evaluate production agent quality by sampling recent MLflow traces and
running judge metrics against them. This enables continuous quality
monitoring without a labelled eval dataset — the production traces ARE
the eval dataset, scored by the same LLM judges used during development.

Usage pattern (nightly Databricks job):
    1. Search recent production traces via MlflowClient.search_traces()
    2. Convert traces to eval rows: {request, response, retrieved_context}
    3. Run mlflow.genai.evaluate() with standard scorers
    4. Log aggregated metrics to the prod MLflow experiment
    5. Alert if any metric drops below threshold

The nightly DAB workflow is defined in:
    bundle/resources/monitoring_workflow.yml

Reference:
    https://mlflow.org/docs/latest/llms/tracing/index.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from framework.config import AgentOpsConfig, get_config
from framework.evaluation.evaluator import EvaluationResult, EvaluationThresholds
from framework.utils.mlflow_utils import set_experiment_for_env

logger = logging.getLogger(__name__)


@dataclass
class OnlineEvalAlert:
    """Triggered when a quality metric drops below threshold."""
    metric_name: str
    actual_value: float
    threshold: float
    trace_count: int

    def message(self) -> str:
        return (
            f"QUALITY ALERT: {self.metric_name}={self.actual_value:.3f} "
            f"< threshold={self.threshold:.3f} "
            f"(evaluated {self.trace_count} production traces)"
        )


class OnlineEvaluator:
    """
    Continuously evaluate production agent quality from live MLflow traces.

    Samples recent traces from the production MLflow experiment, converts
    them to an evaluation dataset, and runs the standard judge scorers.
    Results are logged to the same experiment for long-term trend tracking.

    This class is called nightly by the monitoring DAB workflow.

    Example:
        >>> evaluator = OnlineEvaluator(agent_name="rag_agent", trace_sample_size=50)
        >>> result, alerts = evaluator.run()
        >>> for alert in alerts:
        ...     print(alert.message())
        >>> if alerts:
        ...     # Trigger PagerDuty / Slack / GitHub Issue
        ...     notify_oncall(alerts)
    """

    def __init__(
        self,
        agent_name: str,
        trace_sample_size: int = 50,
        thresholds: Optional[EvaluationThresholds] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        """
        Args:
            agent_name:        Name of the agent to evaluate (matches MLflow tag
                               "agentops.agent_name" on traces).
            trace_sample_size: Number of recent production traces to sample.
                               Higher = more representative but slower.
            thresholds:        Quality gates. Defaults to EvaluationThresholds().
            config:            AgentOpsConfig instance.
        """
        self.agent_name = agent_name
        self.trace_sample_size = trace_sample_size
        self.thresholds = thresholds or EvaluationThresholds()
        self.config = config or get_config()
        self._client = MlflowClient()

    def run(self) -> tuple[EvaluationResult, List[OnlineEvalAlert]]:
        """
        Sample recent traces, evaluate quality, return result and alerts.

        Returns:
            (EvaluationResult, List[OnlineEvalAlert])
            EvaluationResult contains metrics logged to MLflow.
            Alerts list is non-empty if any metric is below threshold.

        Example:
            >>> result, alerts = evaluator.run()
            >>> print(result.summary())
            >>> for alert in alerts:
            ...     print(alert.message())
        """
        exp_id = set_experiment_for_env(self.agent_name, self.config)
        traces = self._fetch_recent_traces(exp_id)

        if not traces:
            logger.warning(
                "No recent traces found for agent '%s' in experiment '%s'. "
                "Skipping online evaluation.",
                self.agent_name, exp_id,
            )
            return (
                EvaluationResult(
                    run_id="",
                    agent_name=self.agent_name,
                    metrics={},
                    thresholds=self.thresholds,
                ),
                [],
            )

        eval_df = self._traces_to_eval_df(traces)
        logger.info(
            "Evaluating %d production traces for agent '%s'.",
            len(eval_df), self.agent_name,
        )

        from mlflow.genai.scorers import RelevanceToQuery, RetrievalGroundedness, Safety

        scorers = [RetrievalGroundedness(), RelevanceToQuery(), Safety()]

        with mlflow.start_run(
            run_name=f"{self.agent_name}_online_eval"
        ) as run:
            mlflow.set_tag("agentops.agent_name", self.agent_name)
            mlflow.set_tag("agentops.env", self.config.env)
            mlflow.set_tag("agentops.eval_type", "online")
            mlflow.log_param("trace_sample_size", len(eval_df))

            # For online eval we don't re-invoke the agent — we evaluate the
            # existing responses captured in the traces.
            results = mlflow.genai.evaluate(
                predict_fn=self._make_passthrough_predict(eval_df),
                data=eval_df,
                scorers=scorers,
            )

            metrics = results.metrics

            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"online_eval.{metric_name}", value)

            logger.info("Online evaluation complete. Run ID: %s", run.info.run_id)

        eval_result = EvaluationResult(
            run_id=run.info.run_id,
            agent_name=self.agent_name,
            metrics=metrics,
            thresholds=self.thresholds,
            eval_table=results.result_df,
        )

        alerts = self._check_thresholds(metrics, trace_count=len(eval_df))
        return eval_result, alerts

    def _fetch_recent_traces(self, experiment_id: str) -> List[Any]:
        """
        Fetch the most recent production traces for this agent.

        Filters by:
          - experiment_id: the prod experiment for this agent
          - agentops.agent_name tag: ensures we only get traces for this agent
          - status = 'OK': exclude error traces from quality scoring
        """
        try:
            traces = self._client.search_traces(
                experiment_ids=[experiment_id],
                filter_string=(
                    f"attributes.status = 'OK' "
                    f"AND tags.agentops.agent_name = '{self.agent_name}'"
                ),
                max_results=self.trace_sample_size,
                order_by=["timestamp_ms DESC"],
            )
            logger.info("Fetched %d traces from experiment %s.", len(traces), experiment_id)
            return traces
        except Exception as exc:
            logger.warning("Failed to fetch traces: %s", exc)
            return []

    def _traces_to_eval_df(self, traces: List[Any]) -> pd.DataFrame:
        """
        Convert MLflow trace objects to an eval DataFrame.

        Extracts from each trace:
          - request:            user input (from trace inputs)
          - response:           agent output (from trace outputs)
          - retrieved_context:  concatenated retriever span outputs (if present)
        """
        rows = []
        for trace in traces:
            try:
                row = self._extract_trace_row(trace)
                if row:
                    rows.append(row)
            except Exception as exc:
                logger.debug("Skipping trace %s: %s", getattr(trace.info, "request_id", "?"), exc)

        if not rows:
            return pd.DataFrame(columns=["request", "response", "retrieved_context"])

        return pd.DataFrame(rows)

    def _extract_trace_row(self, trace: Any) -> Optional[Dict[str, str]]:
        """Extract request/response/context from a single MLflow trace."""
        info = trace.info
        data = trace.data

        # Extract user request from trace inputs
        request = ""
        if data.request:
            import json
            try:
                req_dict = json.loads(data.request) if isinstance(data.request, str) else data.request
                messages = req_dict.get("messages", [])
                user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
                request = user_msgs[-1] if user_msgs else str(data.request)
            except Exception:
                request = str(data.request)

        # Extract response from trace outputs
        response = ""
        if data.response:
            import json
            try:
                resp_dict = json.loads(data.response) if isinstance(data.response, str) else data.response
                response = resp_dict.get("content", str(data.response))
            except Exception:
                response = str(data.response)

        if not request or not response:
            return None

        # Extract retrieved context from RETRIEVER spans
        retrieved_context = self._extract_retriever_context(trace)

        return {
            "request": request,
            "response": response,
            "retrieved_context": retrieved_context,
            "trace_id": getattr(info, "request_id", ""),
        }

    def _extract_retriever_context(self, trace: Any) -> str:
        """Extract concatenated retriever output from trace spans."""
        try:
            for span in (trace.data.spans or []):
                if getattr(span, "span_type", "") in ("RETRIEVER", "retriever"):
                    outputs = getattr(span, "outputs", None) or {}
                    if isinstance(outputs, dict):
                        context = outputs.get("documents") or outputs.get("context") or ""
                        if isinstance(context, list):
                            return "\n\n".join(str(c) for c in context)
                        return str(context)
        except Exception:
            pass
        return ""

    def _make_passthrough_predict(self, eval_df: pd.DataFrame):
        """
        Return a predict_fn that returns the pre-recorded response from the trace.

        This avoids re-invoking the agent — we evaluate the actual responses
        that were served to users.
        """
        response_map = {
            row["request"]: row["response"]
            for _, row in eval_df.iterrows()
        }

        def predict_fn(inputs: dict) -> str:
            request = inputs.get("request", "")
            return response_map.get(request, "")

        return predict_fn

    def _check_thresholds(
        self, metrics: Dict[str, float], trace_count: int
    ) -> List[OnlineEvalAlert]:
        """Check metrics against thresholds and return any triggered alerts."""
        threshold_map = {
            "groundedness": self.thresholds.groundedness,
            "relevance": self.thresholds.relevance,
            "safety": self.thresholds.safety,
        }
        alerts = []
        for metric_fragment, threshold in threshold_map.items():
            if threshold is None:
                continue
            actual = self._find_metric(metrics, metric_fragment)
            if actual is not None and actual < threshold:
                alert = OnlineEvalAlert(
                    metric_name=metric_fragment,
                    actual_value=actual,
                    threshold=threshold,
                    trace_count=trace_count,
                )
                logger.warning(alert.message())
                alerts.append(alert)
        return alerts

    def _find_metric(self, metrics: Dict[str, float], name: str) -> Optional[float]:
        for key, val in metrics.items():
            if name in key.lower() and isinstance(val, (int, float)):
                return val
        return None
