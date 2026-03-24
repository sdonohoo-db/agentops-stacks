"""
MLflow Utilities
================
Thin wrappers ensuring consistent MLflow experiment setup and logging
patterns across all AgentOps environments (dev, staging, prod).

All functions accept an optional `config` parameter; if omitted, they
use `get_config()` for the ambient environment.

Cost tracking:
    LangChain autolog captures token counts (prompt_tokens, completion_tokens)
    as trace attributes. Use log_token_cost() to convert these to estimated
    dollar costs and log them alongside other eval metrics. This provides
    cost-per-query visibility without any extra instrumentation in agent code.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import mlflow
from mlflow.tracking import MlflowClient

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


def get_or_create_experiment(
    name: Optional[str] = None,
    config: Optional[AgentOpsConfig] = None,
) -> str:
    """
    Get or create an MLflow experiment for the current environment.

    Uses the environment-specific path from config if `name` is not provided.

    Args:
        name: Override experiment name/path. If None, uses config.mlflow_experiment_path.
        config: AgentOpsConfig instance. Defaults to get_config().

    Returns:
        experiment_id: The MLflow experiment ID (string).

    Example:
        >>> exp_id = get_or_create_experiment()
        >>> mlflow.set_experiment(experiment_id=exp_id)
    """
    cfg = config or get_config()
    experiment_path = name or cfg.mlflow_experiment_path

    client = MlflowClient()
    experiment = client.get_experiment_by_name(experiment_path)

    if experiment is None:
        experiment_id = client.create_experiment(experiment_path)
        logger.info("Created MLflow experiment '%s' (id=%s)", experiment_path, experiment_id)
    else:
        experiment_id = experiment.experiment_id
        logger.debug("Using existing MLflow experiment '%s' (id=%s)", experiment_path, experiment_id)

    return experiment_id


def setup_autologging(
    log_models: bool = False,
    disable: bool = False,
) -> None:
    """
    Configure MLflow LangChain autologging for agent tracing.

    Enables automatic span capture for LangChain/LangGraph calls,
    tool invocations, and retrieval operations.

    Args:
        log_models: Whether to log the model artifact alongside traces.
                    Keep False during development to avoid bloating the registry.
        disable: Set True to disable autologging (e.g., in unit tests).

    Example:
        >>> setup_autologging()
        >>> # All subsequent LangChain calls will be traced automatically
    """
    if disable:
        mlflow.langchain.autolog(disable=True)
        return

    mlflow.langchain.autolog(
        log_input_examples=True,
        log_model_signatures=True,
        log_models=log_models,
        log_traces=True,
        extra_tags={"agentops.framework": "agentops-redux"},
    )
    logger.debug("MLflow LangChain autologging enabled (log_models=%s)", log_models)


def log_eval_results(
    results: Dict[str, Any],
    run_id: Optional[str] = None,
    config: Optional[AgentOpsConfig] = None,
) -> None:
    """
    Log evaluation results (metrics + tags) to the active MLflow run.

    Accepts the dict returned by `mlflow.genai.evaluate()` and logs
    all scalar metrics plus environment tags.

    Args:
        results: Dict with keys "metrics" (Dict[str, float]) and optionally
                 "eval_table" (pd.DataFrame).
        run_id: Log to a specific run ID. If None, logs to the active run.
        config: AgentOpsConfig instance. Defaults to get_config().

    Example:
        >>> with mlflow.start_run():
        ...     eval_results = evaluator.run(agent, dataset)
        ...     log_eval_results(eval_results)
    """
    cfg = config or get_config()
    client = MlflowClient()
    target_run_id = run_id or mlflow.active_run().info.run_id if mlflow.active_run() else None

    if target_run_id is None:
        logger.warning("No active MLflow run; eval results will not be logged.")
        return

    metrics = results.get("metrics", {})
    for metric_name, value in metrics.items():
        if isinstance(value, (int, float)):
            client.log_metric(target_run_id, f"eval.{metric_name}", value)

    client.set_tag(target_run_id, "agentops.env", cfg.env)
    client.set_tag(target_run_id, "agentops.catalog", cfg.active_catalog)

    logger.info(
        "Logged %d eval metrics to run %s", len(metrics), target_run_id[:8]
    )


def set_experiment_for_env(
    agent_name: str,
    config: Optional[AgentOpsConfig] = None,
) -> str:
    """
    Set (and create if needed) the MLflow experiment for a specific agent
    in the current environment.

    Naming convention: /AgentOps/<env>/<agent_name>

    Args:
        agent_name: Short identifier for the agent (e.g., "rag_agent", "summarizer").
        config: AgentOpsConfig instance. Defaults to get_config().

    Returns:
        experiment_id string.

    Example:
        >>> exp_id = set_experiment_for_env("rag_agent")
        >>> mlflow.set_experiment(experiment_id=exp_id)
    """
    cfg = config or get_config()
    experiment_path = f"{cfg.mlflow_experiment_base}/{cfg.env}/{agent_name}"
    experiment_id = get_or_create_experiment(name=experiment_path, config=cfg)
    mlflow.set_experiment(experiment_id=experiment_id)
    return experiment_id


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

# Default cost estimates per 1000 tokens (USD).
# Override by passing model_cost_per_1k to log_token_cost().
# Values are approximate list prices — update as pricing changes.
_DEFAULT_COST_PER_1K = {
    # Databricks Foundation Model API (meta-llama-3-3-70b-instruct)
    "databricks-meta-llama-3-3-70b-instruct": {"input": 0.00090, "output": 0.00270},
    # Databricks DBRX
    "databricks-dbrx-instruct": {"input": 0.00075, "output": 0.00225},
    # Databricks Mixtral
    "databricks-mixtral-8x7b-instruct": {"input": 0.00050, "output": 0.00150},
    # Catch-all fallback
    "default": {"input": 0.00100, "output": 0.00300},
}


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_endpoint: str = "default",
    cost_per_1k: Optional[Dict[str, float]] = None,
) -> float:
    """
    Estimate the USD cost of a single LLM call from token counts.

    Token counts are captured automatically by mlflow.langchain.autolog().
    Extract them from a trace with get_trace_token_counts().

    Args:
        prompt_tokens:     Number of input/prompt tokens consumed.
        completion_tokens: Number of output/completion tokens generated.
        model_endpoint:    Databricks FM API endpoint name (used to look up
                           per-token pricing).
        cost_per_1k:       Override the default pricing table. Dict with
                           {"input": float, "output": float} per 1k tokens.

    Returns:
        Estimated cost in USD as a float.

    Example:
        >>> cost = estimate_cost(prompt_tokens=1500, completion_tokens=400,
        ...                      model_endpoint="databricks-meta-llama-3-3-70b-instruct")
        >>> print(f"${cost:.4f}")
    """
    pricing = cost_per_1k or _DEFAULT_COST_PER_1K.get(
        model_endpoint, _DEFAULT_COST_PER_1K["default"]
    )
    input_cost = (prompt_tokens / 1000.0) * pricing["input"]
    output_cost = (completion_tokens / 1000.0) * pricing["output"]
    return input_cost + output_cost


def get_trace_token_counts(trace_request_id: str) -> Dict[str, int]:
    """
    Extract prompt and completion token counts from an MLflow trace.

    MLflow LangChain autolog captures token usage in LLM spans. This
    helper aggregates across all LLM spans in the trace.

    Args:
        trace_request_id: The MLflow trace request_id (trace.info.request_id).

    Returns:
        Dict with keys "prompt_tokens" and "completion_tokens".
        Returns zeros if the trace has no LLM spans.

    Example:
        >>> counts = get_trace_token_counts(trace.info.request_id)
        >>> cost = estimate_cost(**counts, model_endpoint=cfg.llm_endpoint)
    """
    client = MlflowClient()
    try:
        trace = client.get_trace(trace_request_id)
        prompt_tokens = 0
        completion_tokens = 0
        for span in (trace.data.spans or []):
            attrs = getattr(span, "attributes", {}) or {}
            prompt_tokens += int(attrs.get("llm.usage.prompt_tokens", 0))
            completion_tokens += int(attrs.get("llm.usage.completion_tokens", 0))
        return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    except Exception as exc:
        logger.debug("Could not extract token counts from trace %s: %s", trace_request_id, exc)
        return {"prompt_tokens": 0, "completion_tokens": 0}


def log_token_cost(
    traces: List[Any],
    model_endpoint: str,
    run_id: Optional[str] = None,
    cost_per_1k: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Compute and log cost metrics from a list of MLflow traces.

    Aggregates token counts across all provided traces, computes total
    and per-query cost estimates, and logs them to the active (or specified)
    MLflow run.

    Intended for use in the batch inferencing and monitoring workflows to
    track cost-per-query trends over time.

    Args:
        traces:        List of MLflow trace objects (from search_traces()).
        model_endpoint: Databricks FM API endpoint name.
        run_id:        Log to a specific run ID. Defaults to active run.
        cost_per_1k:   Override default pricing table.

    Returns:
        Dict with keys: total_prompt_tokens, total_completion_tokens,
        total_cost_usd, avg_cost_per_query_usd.

    Example:
        >>> from mlflow.tracking import MlflowClient
        >>> client = MlflowClient()
        >>> traces = client.search_traces(experiment_ids=[exp_id], max_results=100)
        >>> with mlflow.start_run():
        ...     cost_summary = log_token_cost(traces, model_endpoint=cfg.llm_endpoint)
        ...     print(f"Total cost: ${cost_summary['total_cost_usd']:.4f}")
    """
    total_prompt = 0
    total_completion = 0

    for trace in traces:
        request_id = getattr(trace.info, "request_id", None)
        if not request_id:
            continue
        counts = get_trace_token_counts(request_id)
        total_prompt += counts["prompt_tokens"]
        total_completion += counts["completion_tokens"]

    total_cost = estimate_cost(
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        model_endpoint=model_endpoint,
        cost_per_1k=cost_per_1k,
    )
    avg_cost = total_cost / max(len(traces), 1)

    summary = {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_cost_usd": total_cost,
        "avg_cost_per_query_usd": avg_cost,
    }

    client = MlflowClient()
    target_run_id = run_id
    if target_run_id is None and mlflow.active_run():
        target_run_id = mlflow.active_run().info.run_id

    if target_run_id:
        for key, value in summary.items():
            client.log_metric(target_run_id, f"cost.{key}", value)
        logger.info(
            "Logged cost metrics: total=$%.4f avg=$%.6f (%d traces)",
            total_cost, avg_cost, len(traces),
        )
    else:
        logger.warning("No active MLflow run; cost metrics not logged.")

    return summary
