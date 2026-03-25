"""MCP tool: submit_trace_feedback.

Attach user feedback (thumbs up/down + optional comment) to an MLflow
trace using MlflowClient.set_trace_tag(). This closes the human-in-the-loop
feedback loop from end users back to the observability layer.

The trace_id can be surfaced in the UI by embedding it in agent responses
or by having the serving endpoint return the X-Mlflow-Request-Id header.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def submit_trace_feedback(
    trace_id: str,
    feedback: str,
    comment: Optional[str] = None,
    source: str = "user",
) -> str:
    """
    Attach user or SME feedback to an MLflow trace.

    Tags the trace with:
      - agentops.feedback:        "positive" | "negative" | "neutral"
      - agentops.feedback_source: who submitted the feedback
      - agentops.feedback_comment: optional free-text note

    This enables filtering traces by feedback in the MLflow UI and
    building HITL (Human-in-the-Loop) improvement loops by exporting
    negatively-rated traces as new eval dataset entries.

    Args:
        trace_id: MLflow trace request_id. Available as trace.info.request_id
                  or from the X-Mlflow-Request-Id response header.
        feedback: "positive", "negative", or "neutral".
        comment:  Optional free-text feedback from the user.
        source:   Who submitted: "user", "reviewer", "automated".

    Returns:
        Confirmation message string.

    Example (via MCP):
        >>> submit_trace_feedback(
        ...     trace_id="abc123",
        ...     feedback="negative",
        ...     comment="Response didn't cite the correct policy version",
        ...     source="sme_reviewer",
        ... )
    """
    valid_feedback = {"positive", "negative", "neutral"}
    if feedback not in valid_feedback:
        return (
            f"Invalid feedback value '{feedback}'. "
            f"Must be one of: {', '.join(sorted(valid_feedback))}"
        )

    if not trace_id or not trace_id.strip():
        return "trace_id is required."

    try:
        from mlflow.tracking import MlflowClient
        client = MlflowClient()

        client.set_trace_tag(trace_id, "agentops.feedback", feedback)
        client.set_trace_tag(trace_id, "agentops.feedback_source", source)
        if comment:
            client.set_trace_tag(trace_id, "agentops.feedback_comment", comment[:500])

        logger.info(
            "Feedback '%s' recorded for trace %s (source=%s).",
            feedback, trace_id[:12], source,
        )

        parts = [
            f"Feedback recorded: {feedback.upper()} for trace {trace_id[:12]}...",
            f"Source: {source}",
        ]
        if comment:
            parts.append(f"Comment: {comment}")
        parts.append(
            "\nView in MLflow UI → Traces → filter by tag agentops.feedback."
        )
        return "\n".join(parts)

    except ImportError:
        return "MLflow is not installed. Run: pip install mlflow>=2.17.0"
    except Exception as exc:
        return f"Error recording feedback for trace {trace_id}: {exc}"


def export_negative_traces_as_eval(
    experiment_id: str,
    output_path: str = "reference_agent/eval/hitl_eval_additions.jsonl",
    max_traces: int = 50,
) -> str:
    """
    Export negatively-rated production traces as candidate eval dataset entries.

    Searches for traces tagged with agentops.feedback=negative, formats them
    as JSONL rows matching the eval dataset schema, and writes to a file for
    human review and annotation before merging into eval_dataset.jsonl.

    Args:
        experiment_id: MLflow experiment ID to search.
        output_path:   Where to write the JSONL export (relative to project root).
        max_traces:    Maximum number of negative traces to export.

    Returns:
        Summary message with count of exported traces.

    Example (via MCP):
        >>> export_negative_traces_as_eval(
        ...     experiment_id="123456789",
        ...     output_path="reference_agent/eval/hitl_review.jsonl",
        ... )
    """
    try:
        import json
        from mlflow.tracking import MlflowClient

        client = MlflowClient()

        traces = client.search_traces(
            experiment_ids=[experiment_id],
            filter_string="tags.`agentops.feedback` = 'negative'",
            max_results=max_traces,
            order_by=["timestamp_ms DESC"],
        )

        if not traces:
            return (
                f"No negatively-rated traces found in experiment {experiment_id}. "
                "Submit feedback with feedback='negative' to populate this."
            )

        output_file = PROJECT_ROOT / output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

        rows_written = 0
        with open(output_file, "w", encoding="utf-8") as f:
            for trace in traces:
                try:
                    row = _trace_to_eval_row(trace)
                    if row:
                        f.write(json.dumps(row) + "\n")
                        rows_written += 1
                except Exception:
                    continue

        return (
            f"Exported {rows_written} negatively-rated traces to {output_path}.\n"
            "Review the file, add expected_response fields, then merge into "
            "reference_agent/eval/eval_dataset.jsonl."
        )

    except ImportError:
        return "MLflow is not installed. Run: pip install mlflow>=2.17.0"
    except Exception as exc:
        return f"Error exporting negative traces: {exc}"


def _trace_to_eval_row(trace) -> Optional[dict]:
    """Convert an MLflow trace object to an eval dataset row."""
    import json

    info = trace.info
    data = trace.data

    # Extract request
    request = ""
    if data.request:
        try:
            req = json.loads(data.request) if isinstance(data.request, str) else data.request
            messages = req.get("messages", [])
            user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
            request = user_msgs[-1] if user_msgs else str(data.request)
        except Exception:
            request = str(data.request)

    # Extract actual response (for reference — reviewer should correct it)
    response = ""
    if data.response:
        try:
            resp = json.loads(data.response) if isinstance(data.response, str) else data.response
            response = resp.get("content", str(data.response))
        except Exception:
            response = str(data.response)

    if not request:
        return None

    comment = ""
    for tag in (data.tags or []):
        if getattr(tag, "key", "") == "agentops.feedback_comment":
            comment = getattr(tag, "value", "")

    return {
        "request": request,
        "expected_response": "",  # To be filled in by human reviewer
        "actual_response_at_feedback_time": response,
        "feedback_comment": comment,
        "trace_id": getattr(info, "request_id", ""),
        "_review_status": "pending",
    }
