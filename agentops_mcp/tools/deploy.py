"""MCP tool: deploy_agentops_framework."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent


def deploy_agentops_framework(
    target: str = "dev",
    validate_only: bool = False,
    workflow: Optional[str] = None,
) -> str:
    """
    Deploy the AgentOps framework to a Databricks workspace.

    Args:
        target:        Target environment: "dev", "staging", or "prod".
        validate_only: If True, only validate the bundle without deploying.
        workflow:      Optional workflow name to trigger after deployment.

    Returns:
        Deployment result message with status and manifest location.
    """
    if target not in ("dev", "staging", "prod"):
        return f"Error: target must be 'dev', 'staging', or 'prod'. Got: {target}"

    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "deploy.py"), "--target", target]
    if validate_only:
        cmd.append("--validate-only")
    if workflow:
        cmd.extend(["--workflow", workflow])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            return f"Deployment to '{target}' succeeded.\n\n{result.stdout}"
        else:
            return (
                f"Deployment to '{target}' failed (exit code {result.returncode}).\n\n"
                f"Output:\n{result.stdout}\n\nErrors:\n{result.stderr}"
            )
    except subprocess.TimeoutExpired:
        return "Deployment timed out after 600 seconds."
    except Exception as e:
        return f"Error running deployment: {e}"
