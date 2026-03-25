"""
Deployment Manifest Generator
===============================
Query the Databricks workspace for all deployed AgentOps components
and generate a detailed deployment_manifest.md.

The manifest is:
  - Written to the project root as deployment_manifest.md
  - Machine-readable (YAML frontmatter + structured Markdown)
  - AI-agent-readable (can be parsed by verify.py and monitor tools)

Usage:
    python scripts/generate_manifest.py --target dev
    python scripts/generate_manifest.py --target prod

Called automatically by scripts/deploy.py after deployment.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = PROJECT_ROOT / "deployment_manifest.md"


def get_workspace_client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def get_jobs(client, target: str) -> list[dict]:
    """List all AgentOps jobs deployed to the workspace."""
    jobs = []
    try:
        for job in client.jobs.list():
            if job.settings and job.settings.tags:
                if job.settings.tags.get("agentops_env") == target:
                    jobs.append({
                        "name": job.settings.name or "",
                        "job_id": job.job_id,
                        "url": f"{client.config.host}#job/{job.job_id}",
                        "component": job.settings.tags.get("agentops_component", "unknown"),
                        "status": "DEPLOYED",
                    })
    except Exception as e:
        logger.warning("Could not list jobs: %s", e)
    return jobs


def get_model_serving_endpoint(client, endpoint_name: str) -> dict:
    """Get Model Serving endpoint status."""
    try:
        endpoint = client.serving_endpoints.get(name=endpoint_name)
        state = "READY" if endpoint.state and endpoint.state.ready else "NOT_READY"
        return {
            "name": endpoint_name,
            "url": f"{client.config.host}/serving-endpoints/{endpoint_name}/invocations",
            "state": state,
        }
    except Exception as e:
        return {
            "name": endpoint_name,
            "url": "unknown",
            "state": f"NOT_FOUND ({e})",
        }


def get_mlflow_experiments(config) -> list[dict]:
    """List AgentOps MLflow experiments."""
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow_client = MlflowClient()
    experiments = []
    try:
        for exp in mlflow_client.search_experiments(filter_string="name LIKE '/AgentOps%'"):
            experiments.append({
                "name": exp.name,
                "experiment_id": exp.experiment_id,
                "lifecycle_stage": exp.lifecycle_stage,
            })
    except Exception as e:
        logger.warning("Could not list MLflow experiments: %s", e)
    return experiments


def get_uc_models(client, catalog: str, schema: str) -> list[dict]:
    """List registered models in Unity Catalog."""
    models = []
    try:
        for model in client.registered_models.list(
            catalog_name=catalog,
            schema_name=schema,
        ):
            models.append({
                "name": model.name,
                "full_name": model.full_name,
                "comment": model.comment or "",
            })
    except Exception as e:
        logger.warning("Could not list UC models: %s", e)
    return models


def generate_manifest(target: str) -> str:
    """
    Query the workspace and generate a deployment manifest string.

    Returns:
        Manifest content as a Markdown string.
    """
    os.environ.setdefault("AGENTOPS_ENV", target)
    from framework.config import get_config, AgentOpsConfig

    cfg = AgentOpsConfig(env=target)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    try:
        client = get_workspace_client()
        workspace_url = client.config.host

        jobs = get_jobs(client, target)
        endpoint_info = get_model_serving_endpoint(client, cfg.model_serving_endpoint)
        experiments = get_mlflow_experiments(cfg)
        models = get_uc_models(client, cfg.active_catalog, cfg.active_schema)

        overall_status = "SUCCESS" if jobs and endpoint_info["state"] == "READY" else "PARTIAL"

    except Exception as e:
        logger.error("Failed to query workspace: %s", e)
        workspace_url = os.environ.get("DATABRICKS_HOST", "unknown")
        jobs = []
        endpoint_info = {"name": cfg.model_serving_endpoint, "url": "unknown", "state": "UNKNOWN"}
        experiments = []
        models = []
        overall_status = "FAILED"

    # Build manifest content
    lines = [
        "---",
        f"title: AgentOps Deployment Manifest",
        f"target: {target}",
        f"timestamp: {timestamp}",
        f"workspace: {workspace_url}",
        f"deployment_status: {overall_status}",
        "---",
        "",
        f"# AgentOps Deployment Manifest",
        "",
        f"> **Deployment Status**: `{overall_status}`  ",
        f"> **Environment**: `{target}`  ",
        f"> **Workspace**: {workspace_url}  ",
        f"> **Generated**: {timestamp}",
        "",
        "---",
        "",
        "## Deployed Workflows",
        "",
    ]

    if jobs:
        lines += ["| Workflow | Job ID | Status | URL |", "|---|---|---|---|"]
        for job in jobs:
            lines.append(f"| {job['name']} | {job['job_id']} | {job['status']} | [Open]({job['url']}) |")
    else:
        lines.append("_No workflows found (or workspace not accessible)_")

    lines += [
        "",
        "## Model Serving Endpoint",
        "",
        f"| Endpoint | State | Invocation URL |",
        f"|---|---|---|",
        f"| {endpoint_info['name']} | {endpoint_info['state']} | {endpoint_info['url']} |",
        "",
        "## Unity Catalog Models",
        "",
    ]

    if models:
        lines += ["| Model | Full Name | Description |", "|---|---|---|"]
        for model in models:
            lines.append(f"| {model['name']} | {model['full_name']} | {model['comment']} |")
    else:
        lines.append("_No registered models found_")

    lines += [
        "",
        "## MLflow Experiments",
        "",
    ]

    if experiments:
        lines += ["| Experiment | ID | Status |", "|---|---|---|"]
        for exp in experiments:
            lines.append(f"| {exp['name']} | {exp['experiment_id']} | {exp['lifecycle_stage']} |")
    else:
        lines.append("_No AgentOps MLflow experiments found_")

    lines += [
        "",
        "## Catalog Assets",
        "",
        f"| Asset Type | Catalog | Schema |",
        f"|---|---|---|",
        f"| Vector Search Index | {cfg.active_catalog} | {cfg.active_schema} |",
        f"| Document Chunks Table | {cfg.active_catalog} | {cfg.active_schema} |",
        f"| Eval Dataset Table | {cfg.active_catalog} | {cfg.active_schema} |",
        f"| Batch Results Table | {cfg.active_catalog} | {cfg.active_schema} |",
        "",
        "## Verification",
        "",
        "To verify this deployment, run:",
        "```bash",
        f"python scripts/verify.py --target {target}",
        "```",
        "",
        "---",
        "_This manifest was auto-generated by `scripts/generate_manifest.py`._",
    ]

    return "\n".join(lines)


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print(f"Generating deployment manifest for target '{args.target}'...")

    content = generate_manifest(args.target)

    output_path = Path(args.output) if args.output else MANIFEST_PATH
    output_path.write_text(content, encoding="utf-8")

    print(f"Manifest written to: {output_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AgentOps deployment manifest")
    parser.add_argument("--target", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--output", help="Output file path (default: deployment_manifest.md)")
    args = parser.parse_args()
    sys.exit(main(args))
