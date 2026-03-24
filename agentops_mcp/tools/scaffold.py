"""MCP tool: scaffold_agent_project."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def scaffold_agent_project(
    agent_name: str,
    description: str,
    agent_type: str = "generic",
) -> str:
    """
    Scaffold a new agent project from AgentOps templates.

    Args:
        agent_name:  Snake_case agent name (e.g., "policy_lookup_agent").
        description: What the agent does.
        agent_type:  Template type: "rag", "summarization", or "generic".

    Returns:
        List of created files and next steps.
    """
    if not agent_name.replace("_", "").isalnum():
        return "Error: agent_name must be snake_case alphanumeric (e.g., 'my_agent')"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "scaffold.py"),
        "--name", agent_name,
        "--description", description,
        "--type", agent_type,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return f"Agent '{agent_name}' scaffolded successfully.\n\n{result.stdout}"
        else:
            return f"Scaffolding failed.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}"
    except Exception as e:
        return f"Error scaffolding agent: {e}"
