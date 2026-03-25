"""
AgentOps Framework Deployment Script
======================================
Deploy the AgentOps framework to a Databricks workspace using
Databricks Asset Bundles (DAB).

Usage:
    python scripts/deploy.py --target dev
    python scripts/deploy.py --target staging
    python scripts/deploy.py --target prod
    python scripts/deploy.py --target dev --validate-only
    python scripts/deploy.py --target dev --workflow data_preparation_workflow

What this script does:
    1. Validate bundle configuration (databricks bundle validate)
    2. Deploy to the target workspace (databricks bundle deploy)
    3. Generate deployment manifest (scripts/generate_manifest.py)
    4. Print deployment summary

Prerequisites:
    - Databricks CLI installed (pip install databricks-cli or brew install databricks)
    - Databricks profile configured (databricks configure)
    - Unity Catalog catalogs created (see docs/deployment.md)

Exit codes:
    0 - Deployment successful
    1 - Deployment failed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


def run_command(
    cmd: list[str],
    cwd: Path = PROJECT_ROOT,
    capture: bool = True,
) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=capture,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def build_wheel() -> bool:
    """Build the Python wheel required by all DAB workflow tasks."""
    print("Building wheel (required by DAB python_wheel_task)...")
    code, _, stderr = run_command([sys.executable, "-m", "build"])
    if code != 0:
        print(f"Wheel build FAILED:\n{stderr}")
        return False
    print("Wheel built: dist/agentops_framework-*.whl")
    return True


def validate_bundle(target: str) -> bool:
    """Run databricks bundle validate for the target."""
    print(f"Validating bundle for target '{target}'...")
    code, stdout, stderr = run_command(
        ["databricks", "bundle", "validate", "--target", target]
    )
    if code != 0:
        print(f"Bundle validation FAILED:\n{stderr}")
        return False
    print("Bundle validation: OK")
    return True


def deploy_bundle(target: str, force: bool = False) -> bool:
    """Run databricks bundle deploy for the target."""
    print(f"\nDeploying AgentOps to target '{target}'...")
    cmd = ["databricks", "bundle", "deploy", "--target", target]
    if force:
        cmd.append("--force")

    code, stdout, stderr = run_command(cmd, capture=False)
    if code != 0:
        print(f"\nDeployment FAILED (exit code {code})")
        return False

    print("\nDeployment: OK")
    return True


def trigger_workflow(workflow_name: str, target: str) -> bool:
    """Trigger a specific workflow job."""
    print(f"\nTriggering workflow '{workflow_name}' in target '{target}'...")
    code, stdout, stderr = run_command([
        "databricks", "bundle", "run", workflow_name, "--target", target
    ], capture=False)
    return code == 0


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    start_time = datetime.utcnow()
    target = args.target

    print(f"\n{'='*60}")
    print(f"  AgentOps Framework Deployment")
    print(f"  Target:  {target}")
    print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*60}\n")

    # Step 1: Build wheel
    if not build_wheel():
        return 1

    # Step 2: Validate
    if not validate_bundle(target):
        return 1

    if args.validate_only:
        print("\nValidation-only mode: skipping deployment.")
        return 0

    # Step 3: Deploy
    if not deploy_bundle(target, force=args.force):
        return 1

    # Step 4: Trigger specific workflow if requested
    if args.workflow:
        if not trigger_workflow(args.workflow, target):
            print(f"Warning: Workflow '{args.workflow}' trigger failed.")

    # Step 5: Generate manifest
    print("\nGenerating deployment manifest...")
    manifest_code, _, _ = run_command([
        sys.executable, "scripts/generate_manifest.py",
        "--target", target,
    ])
    if manifest_code != 0:
        print("Warning: Manifest generation failed. Deployment continues.")
    else:
        print("Manifest generated: deployment_manifest.md")

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"  Deployment Complete")
    print(f"  Duration: {duration:.1f}s")
    print(f"  Manifest: deployment_manifest.md")
    print(f"\n  Next steps:")
    print(f"    1. Review deployment_manifest.md")
    print(f"    2. Run: python scripts/verify.py --target {target}")
    print(f"    3. Check MLflow experiments for evaluation results")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy AgentOps framework to a Databricks workspace"
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=["dev", "staging", "prod"],
        help="Deployment target environment",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the bundle, do not deploy",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deploy even if resources already exist",
    )
    parser.add_argument(
        "--workflow",
        help="Trigger a specific workflow after deployment",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()
    sys.exit(main(args))
