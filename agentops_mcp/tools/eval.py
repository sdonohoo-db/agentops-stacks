"""MCP tool: run_evaluation_suite."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_evaluation_suite(
    agent: str = "all",
    sample_size: int = 0,
    strict: bool = False,
) -> str:
    """
    Run the automated evaluation suite for AgentOps agents.

    Args:
        agent:       Which agent to evaluate: "rag_agent", "summarization_agent", or "all".
        sample_size: If > 0, sample this many eval rows (faster for dev iteration).
        strict:      Use stricter thresholds (for staging→prod promotion gate).

    Returns:
        Evaluation results with metrics and pass/fail status.
    """
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "reference_agent" / "eval" / "run_eval.py"),
        "--agent", agent,
    ]
    if sample_size > 0:
        cmd.extend(["--sample", str(sample_size)])
    if strict:
        cmd.append("--strict")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "AGENTOPS_ENV": "dev"},
        )
        status = "PASSED" if result.returncode == 0 else "FAILED"
        return f"Evaluation {status} (exit code {result.returncode}).\n\n{result.stdout}"
    except subprocess.TimeoutExpired:
        return "Evaluation timed out after 600 seconds."
    except Exception as e:
        return f"Error running evaluation: {e}"
