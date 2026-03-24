"""
Databricks SDK Utilities
========================
Thin wrappers around the Databricks Python SDK for common AgentOps
operations: workspace info, secrets, and job run monitoring.

Uses `databricks-sdk` with automatic authentication via:
  1. DATABRICKS_HOST + DATABRICKS_TOKEN env vars
  2. ~/.databrickscfg profile
  3. Databricks cluster runtime (when running as a job)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState

logger = logging.getLogger(__name__)

_workspace_client: Optional[WorkspaceClient] = None


def get_workspace_client(reload: bool = False) -> WorkspaceClient:
    """
    Return a singleton Databricks WorkspaceClient.

    Authentication order:
        1. Environment variables (DATABRICKS_HOST, DATABRICKS_TOKEN)
        2. ~/.databrickscfg DEFAULT profile
        3. Databricks cluster runtime credentials

    Args:
        reload: Force re-instantiation (useful in tests).

    Returns:
        Authenticated WorkspaceClient instance.

    Example:
        >>> client = get_workspace_client()
        >>> print(client.current_user.me().user_name)
    """
    global _workspace_client
    if _workspace_client is None or reload:
        _workspace_client = WorkspaceClient()
    return _workspace_client


def get_secret(scope: str, key: str) -> str:
    """
    Retrieve a Databricks secret value from a secret scope.

    Args:
        scope: Secret scope name (e.g., "agentops-secrets").
        key:   Secret key name (e.g., "openai-api-key").

    Returns:
        Secret value as a plain string.

    Example:
        >>> api_key = get_secret("agentops-secrets", "llm-api-key")
    """
    client = get_workspace_client()
    secret_bytes = client.secrets.get_secret(scope=scope, key=key)
    return secret_bytes.value


def wait_for_job_run(
    job_id: int,
    run_id: int,
    poll_interval_seconds: int = 15,
    timeout_seconds: int = 3600,
) -> RunResultState:
    """
    Poll a Databricks job run until it completes or times out.

    Args:
        job_id:                  Databricks job ID.
        run_id:                  Databricks run ID for the specific run.
        poll_interval_seconds:   Seconds between status checks (default: 15).
        timeout_seconds:         Max wait time in seconds (default: 3600).

    Returns:
        RunResultState: SUCCESS, FAILED, TIMEDOUT, or CANCELED.

    Raises:
        TimeoutError: If the run does not complete within timeout_seconds.
        RuntimeError: If the run reaches a failed terminal state.

    Example:
        >>> result = wait_for_job_run(job_id=123, run_id=456)
        >>> assert result == RunResultState.SUCCESS
    """
    client = get_workspace_client()
    elapsed = 0

    while elapsed < timeout_seconds:
        run = client.jobs.get_run(run_id=run_id)
        state = run.state

        if state.life_cycle_state in (
            RunLifeCycleState.TERMINATED,
            RunLifeCycleState.SKIPPED,
            RunLifeCycleState.INTERNAL_ERROR,
        ):
            result = state.result_state
            logger.info(
                "Job %d / Run %d completed: %s", job_id, run_id, result
            )
            return result

        logger.debug(
            "Job %d / Run %d: %s (elapsed %ds)",
            job_id,
            run_id,
            state.life_cycle_state,
            elapsed,
        )
        time.sleep(poll_interval_seconds)
        elapsed += poll_interval_seconds

    raise TimeoutError(
        f"Job {job_id} / Run {run_id} did not complete within {timeout_seconds}s"
    )


def get_workspace_url() -> str:
    """
    Return the current workspace URL (e.g., https://adb-xxx.azuredatabricks.net).

    Example:
        >>> url = get_workspace_url()
        >>> print(url)
        https://adb-1234567890.12.azuredatabricks.net
    """
    client = get_workspace_client()
    return client.config.host


def trigger_job(job_id: int, params: Optional[dict] = None) -> int:
    """
    Trigger a Databricks job run and return the run_id.

    Args:
        job_id: The Databricks job ID to trigger.
        params: Optional notebook/task parameters dict.

    Returns:
        run_id: The run ID of the triggered job run.

    Example:
        >>> run_id = trigger_job(job_id=123, params={"env": "staging"})
    """
    client = get_workspace_client()
    notebook_params = params or {}
    run = client.jobs.run_now(job_id=job_id, notebook_params=notebook_params)
    logger.info("Triggered job %d → run_id=%d", job_id, run.run_id)
    return run.run_id
