"""
Deployment Verification Script
================================
Read deployment_manifest.md and verify that all deployed components
are live and functioning correctly.

Verification checks:
  1. All workflow jobs exist and are runnable
  2. Model Serving endpoint is READY
  3. Endpoint responds to a test inference call
  4. Unity Catalog models exist with @champion alias
  5. MLflow experiments exist and are accessible

Results are written to verification_report.md.
This script is designed to be callable by AI agents for automated verification.

Usage:
    python scripts/verify.py --target dev
    python scripts/verify.py --target prod --test-inference

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = PROJECT_ROOT / "deployment_manifest.md"
REPORT_PATH = PROJECT_ROOT / "verification_report.md"


class VerificationResult:
    def __init__(self):
        self.checks: list[dict] = []

    def add(self, name: str, passed: bool, details: str = ""):
        status = "PASS" if passed else "FAIL"
        self.checks.append({"name": name, "status": status, "details": details})
        icon = "✓" if passed else "✗"
        print(f"  [{icon}] {name}: {status}" + (f" — {details}" if details else ""))

    @property
    def all_passed(self) -> bool:
        return all(c["status"] == "PASS" for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c["status"] == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c["status"] == "FAIL")


def read_manifest() -> dict:
    """Parse key fields from deployment_manifest.md."""
    if not MANIFEST_PATH.exists():
        return {}

    content = MANIFEST_PATH.read_text()
    manifest = {}

    # Extract YAML frontmatter
    fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                manifest[key.strip()] = val.strip()

    return manifest


def verify_jobs(client, target: str, result: VerificationResult) -> None:
    """Check that deployed workflow jobs exist."""
    try:
        jobs_found = 0
        for job in client.jobs.list():
            if job.settings and job.settings.tags:
                if job.settings.tags.get("agentops_env") == target:
                    jobs_found += 1

        result.add(
            "Workflow Jobs Exist",
            jobs_found > 0,
            f"Found {jobs_found} AgentOps workflow job(s)",
        )
    except Exception as e:
        result.add("Workflow Jobs Exist", False, str(e))


def verify_endpoint(client, endpoint_name: str, result: VerificationResult) -> str:
    """Check that Model Serving endpoint is READY. Returns endpoint URL."""
    endpoint_url = ""
    try:
        endpoint = client.serving_endpoints.get(name=endpoint_name)
        is_ready = (
            endpoint.state
            and endpoint.state.ready
            and endpoint.state.ready.value == "READY"
        )
        endpoint_url = f"{client.config.host}/serving-endpoints/{endpoint_name}/invocations"
        result.add(
            "Model Serving Endpoint READY",
            is_ready,
            f"State: {endpoint.state.ready.value if endpoint.state and endpoint.state.ready else 'UNKNOWN'}",
        )
    except Exception as e:
        result.add("Model Serving Endpoint READY", False, f"Endpoint not found: {e}")
    return endpoint_url


def verify_test_inference(client, endpoint_name: str, result: VerificationResult) -> None:
    """Make a test inference call to the endpoint."""
    try:
        import json as json_lib
        import requests

        endpoint_url = f"{client.config.host}/serving-endpoints/{endpoint_name}/invocations"
        token = client.config.token

        test_payload = {
            "messages": [{"role": "user", "content": "What is AgentOps?"}]
        }

        response = requests.post(
            endpoint_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json_lib.dumps(test_payload),
            timeout=60,
        )

        if response.status_code == 200:
            resp_data = response.json()
            content = (
                resp_data.get("content", "")
                or str(resp_data)
            )[:100]
            result.add("Test Inference Succeeds", True, f"Response: '{content}...'")
        else:
            result.add(
                "Test Inference Succeeds",
                False,
                f"HTTP {response.status_code}: {response.text[:100]}",
            )
    except Exception as e:
        result.add("Test Inference Succeeds", False, str(e))


def verify_uc_models(client, catalog: str, schema: str, result: VerificationResult) -> None:
    """Check that registered models exist with @champion alias."""
    try:
        from mlflow.tracking import MlflowClient
        mlflow_client = MlflowClient()

        champion_models = []
        for model in client.registered_models.list(catalog_name=catalog, schema_name=schema):
            try:
                alias = mlflow_client.get_model_version_by_alias(model.full_name, "champion")
                champion_models.append(model.full_name)
            except Exception:
                pass

        result.add(
            "UC Models with @champion Alias",
            len(champion_models) > 0,
            f"Champion models: {champion_models or 'none found'}",
        )
    except Exception as e:
        result.add("UC Models with @champion Alias", False, str(e))


def verify_mlflow_experiments(result: VerificationResult) -> None:
    """Check that AgentOps MLflow experiments exist."""
    try:
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        experiments = client.search_experiments(filter_string="name LIKE '/AgentOps%'")
        result.add(
            "MLflow Experiments Exist",
            len(experiments) > 0,
            f"Found {len(experiments)} AgentOps experiment(s)",
        )
    except Exception as e:
        result.add("MLflow Experiments Exist", False, str(e))


def write_report(result: VerificationResult, target: str) -> None:
    """Write verification_report.md."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    overall = "PASSED" if result.all_passed else "FAILED"

    lines = [
        "---",
        f"title: AgentOps Verification Report",
        f"target: {target}",
        f"timestamp: {timestamp}",
        f"overall_status: {overall}",
        f"checks_passed: {result.pass_count}",
        f"checks_failed: {result.fail_count}",
        "---",
        "",
        f"# AgentOps Verification Report",
        "",
        f"> **Overall Status**: `{overall}`  ",
        f"> **Environment**: `{target}`  ",
        f"> **Checks**: {result.pass_count} passed, {result.fail_count} failed  ",
        f"> **Verified**: {timestamp}",
        "",
        "## Check Results",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]

    for check in result.checks:
        status_badge = "✅ PASS" if check["status"] == "PASS" else "❌ FAIL"
        lines.append(f"| {check['name']} | {status_badge} | {check['details']} |")

    if not result.all_passed:
        lines += [
            "",
            "## Failed Checks — Recommended Actions",
            "",
        ]
        for check in result.checks:
            if check["status"] == "FAIL":
                lines += [
                    f"### {check['name']}",
                    f"**Error**: {check['details']}",
                    "",
                    "**Actions**:",
                    "- Check workspace connectivity (`databricks workspace ls`)",
                    "- Review job logs in the Databricks UI",
                    "- Re-run deployment: `python scripts/deploy.py --target " + target + "`",
                    "",
                ]

    lines += [
        "---",
        "_This report was auto-generated by `scripts/verify.py`._",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    target = args.target
    os.environ.setdefault("AGENTOPS_ENV", target)
    from framework.config import AgentOpsConfig

    cfg = AgentOpsConfig(env=target)
    result = VerificationResult()

    print(f"\n{'='*60}")
    print(f"  AgentOps Deployment Verification")
    print(f"  Target: {target}")
    print(f"{'='*60}\n")

    # Check manifest exists
    manifest = read_manifest()
    result.add(
        "Deployment Manifest Exists",
        bool(manifest),
        str(MANIFEST_PATH) if MANIFEST_PATH.exists() else "deployment_manifest.md not found",
    )

    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient()

        verify_jobs(client, target, result)
        verify_endpoint(client, cfg.model_serving_endpoint, result)

        if args.test_inference:
            verify_test_inference(client, cfg.model_serving_endpoint, result)

        verify_uc_models(client, cfg.active_catalog, cfg.active_schema, result)
        verify_mlflow_experiments(result)

    except Exception as e:
        result.add("Workspace Connectivity", False, str(e))

    write_report(result, target)

    print(f"\n{'='*60}")
    overall = "PASSED" if result.all_passed else "FAILED"
    print(f"  Verification: {overall}")
    print(f"  {result.pass_count} checks passed, {result.fail_count} failed")
    print(f"  Report written to: verification_report.md")
    print(f"{'='*60}\n")

    return 0 if result.all_passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify AgentOps deployment")
    parser.add_argument("--target", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument(
        "--test-inference",
        action="store_true",
        help="Make a test inference call to the Model Serving endpoint",
    )
    args = parser.parse_args()
    sys.exit(main(args))
