"""
AgentOps MCP Server
====================
FastMCP server exposing AgentOps operations as callable tools for
Claude Code and other MCP-compatible clients.

Tools exposed:
  - deploy_agentops_framework   : Deploy to a Databricks workspace
  - scaffold_agent_project       : Scaffold a new agent from templates
  - run_evaluation_suite         : Run agent evaluation and return results
  - read_deployment_manifest     : Read and parse deployment_manifest.md
  - monitor_deployment           : Check endpoint health and trace quality
  - submit_trace_feedback        : Attach user/SME feedback to an MLflow trace
  - export_negative_traces       : Export negatively-rated traces for eval dataset

Platform Installation
---------------------
This server works with any MCP-compatible coding platform.

Claude Code (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "agentops": {
          "command": "python",
          "args": ["/path/to/agentops-redux/agentops_mcp/server.py"],
          "env": {
            "DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
            "DATABRICKS_TOKEN": "dapi...",
            "AGENTOPS_PROJECT_ROOT": "/path/to/agentops-redux"
          }
        }
      }
    }

Cursor: already configured via .cursor/mcp.json in this repo.
    Set DATABRICKS_HOST and DATABRICKS_TOKEN as environment variables or in
    Cursor settings → MCP → environment overrides.

Windsurf: already configured via .windsurf/mcp.json in this repo.
    Set DATABRICKS_HOST and DATABRICKS_TOKEN as environment variables.

Codex: add to your Codex MCP config:
    {
      "mcpServers": {
        "agentops": {
          "command": "python",
          "args": ["agentops_mcp/server.py"],
          "env": {
            "DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
            "DATABRICKS_TOKEN": "dapi...",
            "AGENTOPS_PROJECT_ROOT": "."
          }
        }
      }
    }

Usage:
    python agentops_mcp/server.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Add project root to path so agentops_mcp package and framework are importable.
# NOTE: Do NOT insert project root before sys.path[0] if running as a module,
# as that would shadow the installed `mcp` package with the local directory.
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: 'mcp' package not installed. Run: pip install mcp[cli]", file=sys.stderr)
    sys.exit(1)

from agentops_mcp.tools.deploy import deploy_agentops_framework as _deploy
from agentops_mcp.tools.eval import run_evaluation_suite as _eval
from agentops_mcp.tools.feedback import export_negative_traces_as_eval as _export_feedback
from agentops_mcp.tools.feedback import submit_trace_feedback as _feedback
from agentops_mcp.tools.manifest import read_deployment_manifest as _manifest
from agentops_mcp.tools.monitor import monitor_deployment as _monitor
from agentops_mcp.tools.scaffold import scaffold_agent_project as _scaffold

mcp = FastMCP("AgentOps")


@mcp.tool()
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
    return _deploy(target=target, validate_only=validate_only, workflow=workflow)


@mcp.tool()
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
    return _scaffold(agent_name=agent_name, description=description, agent_type=agent_type)


@mcp.tool()
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
    return _eval(agent=agent, sample_size=sample_size, strict=strict)


@mcp.tool()
def read_deployment_manifest() -> str:
    """
    Read and return the current deployment manifest.

    Returns:
        Deployment manifest content or a message if no manifest exists.
    """
    return _manifest()


@mcp.tool()
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
    return _monitor(target=target, run_verification=run_verification)


@mcp.tool()
def submit_trace_feedback(
    trace_id: str,
    feedback: str,
    comment: Optional[str] = None,
    source: str = "user",
) -> str:
    """
    Attach user or SME feedback to an MLflow trace.

    Args:
        trace_id: MLflow trace request_id (from trace.info.request_id or
                  the X-Mlflow-Request-Id response header).
        feedback: "positive", "negative", or "neutral".
        comment:  Optional free-text note explaining the rating.
        source:   Who submitted: "user", "reviewer", or "automated".

    Returns:
        Confirmation message.
    """
    return _feedback(trace_id=trace_id, feedback=feedback, comment=comment, source=source)


@mcp.tool()
def export_negative_traces(
    experiment_id: str,
    output_path: str = "reference_agent/eval/hitl_eval_additions.jsonl",
    max_traces: int = 50,
) -> str:
    """
    Export negatively-rated production traces as candidate eval dataset entries.

    Searches for traces tagged agentops.feedback=negative, writes them as
    JSONL for human review and annotation before merging into the eval dataset.

    Args:
        experiment_id: MLflow experiment ID to search.
        output_path:   Output JSONL path (relative to project root).
        max_traces:    Maximum traces to export.

    Returns:
        Summary of exported traces and next steps.
    """
    return _export_feedback(
        experiment_id=experiment_id,
        output_path=output_path,
        max_traces=max_traces,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mcp.run()
