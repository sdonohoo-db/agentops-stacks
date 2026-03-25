"""MCP tool: read_deployment_manifest."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def read_deployment_manifest() -> str:
    """
    Read and return the current deployment manifest.

    Returns:
        Deployment manifest content or a message if no manifest exists.
    """
    manifest_path = PROJECT_ROOT / "deployment_manifest.md"
    report_path = PROJECT_ROOT / "verification_report.md"

    if not manifest_path.exists():
        return (
            "No deployment_manifest.md found. "
            "Run 'python scripts/deploy.py --target dev' to deploy first."
        )

    content = manifest_path.read_text(encoding="utf-8")

    if report_path.exists():
        report = report_path.read_text(encoding="utf-8")
        return f"# Deployment Manifest\n\n{content}\n\n---\n\n# Verification Report\n\n{report}"

    return content
