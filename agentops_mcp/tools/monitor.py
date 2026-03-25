"""MCP tool: monitor_deployment."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def monitor_deployment(
    target: str = "prod",
    run_verification: bool = False,
) -> str:
    """
    Check the health of a running AgentOps deployment.

    Reads the deployment manifest and optionally runs fresh verification checks.

    Args:
        target:           Environment to monitor: "dev", "staging", or "prod".
        run_verification: If True, run scripts/verify.py for live checks.

    Returns:
        Health status summary with endpoint state and recommendations.
    """
    manifest_path = PROJECT_ROOT / "deployment_manifest.md"
    if not manifest_path.exists():
        return f"No deployment manifest found for target '{target}'. Deploy first."

    manifest_content = manifest_path.read_text(encoding="utf-8")

    if not run_verification:
        return (
            f"Current deployment manifest:\n\n{manifest_content}\n\n"
            "To run live verification checks, call with run_verification=True."
        )

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "verify.py"),
        "--target", target,
        "--test-inference",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "AGENTOPS_ENV": target},
        )
        status = "HEALTHY" if result.returncode == 0 else "ISSUES DETECTED"
        report_path = PROJECT_ROOT / "verification_report.md"
        report = report_path.read_text() if report_path.exists() else result.stdout
        return f"Monitoring Status: {status}\n\n{report}"
    except Exception as e:
        return f"Error running verification: {e}"
