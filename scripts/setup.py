"""
AgentOps Framework — One-Time Workspace Setup
==============================================
Bootstrap the Databricks workspace resources required before running
scripts/deploy.py for the first time. Safe to re-run — all operations
are idempotent.

What this script does:
    1. Validates prerequisites (Python version, env vars, Databricks CLI)
    2. Verifies workspace connectivity
    3. Installs Python dependencies
    4. Creates Unity Catalog catalogs and schemas (dev + prod)
    5. Creates the Vector Search endpoint
    6. Creates MLflow experiments for all environments
    7. Runs unit tests as a smoke test
    8. Prints a "what to do next" summary

Usage:
    python scripts/setup.py
    python scripts/setup.py --skip-install      # skip pip install
    python scripts/setup.py --skip-tests        # skip unit tests
    python scripts/setup.py --wait-for-vs       # wait until VS endpoint is ONLINE
    python scripts/setup.py --env prod          # target prod workspace instead of dev

Prerequisites:
    export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
    export DATABRICKS_TOKEN=dapi...
    export AGENTOPS_ENV=dev

This script does NOT:
    - Deploy DAB workflows  →  use scripts/deploy.py for that
    - Build the Python wheel →  done automatically by scripts/deploy.py
    - Run inference tests    →  use scripts/verify.py --test-inference for that
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent

# ── ANSI colour helpers ───────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str)   -> None: print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg: str) -> None: print(f"  {YELLOW}!{RESET}  {msg}")
def fail(msg: str) -> None: print(f"  {RED}✗{RESET}  {msg}")
def step(msg: str) -> None: print(f"\n{BOLD}{msg}{RESET}")


# ── Step helpers ──────────────────────────────────────────────────────────────

def check_prerequisites() -> bool:
    """Validate Python version and required environment variables."""
    step("Step 1/7 — Checking prerequisites")
    passed = True

    # Python version
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 11):
        ok(f"Python {major}.{minor}")
    else:
        fail(f"Python {major}.{minor} — requires 3.11+. Install via pyenv or system package manager.")
        passed = False

    # Required env vars
    required = {
        "DATABRICKS_HOST":  "Databricks workspace URL (e.g. https://yourworkspace.azuredatabricks.net)",
        "DATABRICKS_TOKEN": "Databricks personal access token (generate at Settings > Developer)",
        "AGENTOPS_ENV":     "Target environment: dev | staging | prod",
    }
    for var, hint in required.items():
        val = os.environ.get(var, "")
        if val:
            display = val if var != "DATABRICKS_TOKEN" else f"{val[:8]}…"
            ok(f"{var}={display}")
        else:
            fail(f"{var} is not set — {hint}")
            passed = False

    # Databricks CLI
    result = subprocess.run(
        ["databricks", "--version"], capture_output=True, text=True
    )
    if result.returncode == 0:
        ok(f"Databricks CLI: {result.stdout.strip()}")
    else:
        warn("Databricks CLI not found. Install with: pip install databricks-cli")
        warn("  (not required for setup, but needed for deploy)")

    return passed


def verify_connectivity() -> bool:
    """Confirm the workspace credentials actually work."""
    step("Step 2/7 — Verifying workspace connectivity")
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
        )
        me = w.current_user.me()
        ok(f"Connected as: {me.user_name}")
        ok(f"Workspace:    {os.environ['DATABRICKS_HOST']}")
        return True
    except ImportError:
        warn("databricks-sdk not yet installed — skipping connectivity check.")
        warn("  It will be installed in the next step.")
        return True  # Not a hard failure; install step will fix it
    except Exception as exc:
        fail(f"Workspace connection failed: {exc}")
        fail("  Check DATABRICKS_HOST and DATABRICKS_TOKEN are correct.")
        return False


def install_dependencies(skip: bool) -> bool:
    """Install the framework and its dev dependencies."""
    step("Step 3/7 — Installing Python dependencies")
    if skip:
        warn("Skipped (--skip-install)")
        return True

    print("  Running: pip install -e '.[dev]'")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]", "--quiet"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode == 0:
        ok("Dependencies installed")
        return True
    else:
        fail("pip install failed — check pyproject.toml and network access")
        return False


def setup_unity_catalog(
    dev_catalog: str,
    dev_schema: str,
    prod_catalog: str,
    prod_schema: str,
) -> bool:
    """Create Unity Catalog catalogs and schemas idempotently."""
    step("Step 4/7 — Setting up Unity Catalog")
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.errors import ResourceAlreadyExists, PermissionDenied, NotFound
    except ImportError:
        fail("databricks-sdk not installed — run without --skip-install first.")
        return False

    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    resources = [
        (dev_catalog,  dev_schema,  "dev"),
        (prod_catalog, prod_schema, "prod"),
    ]

    all_ok = True
    for catalog_name, schema_name, label in resources:
        # Catalog
        try:
            w.catalogs.create(name=catalog_name)
            ok(f"Created catalog:       {catalog_name}  [{label}]")
        except ResourceAlreadyExists:
            ok(f"Catalog exists:        {catalog_name}  [{label}]")
        except PermissionDenied:
            warn(f"Cannot create catalog {catalog_name} — requires Metastore Admin.")
            warn( "  Create it manually: CREATE CATALOG IF NOT EXISTS {catalog_name}")
            all_ok = False
        except Exception as exc:
            fail(f"Catalog {catalog_name}: {exc}")
            all_ok = False

        # Schema
        try:
            w.schemas.create(name=schema_name, catalog_name=catalog_name)
            ok(f"Created schema:        {catalog_name}.{schema_name}")
        except ResourceAlreadyExists:
            ok(f"Schema exists:         {catalog_name}.{schema_name}")
        except (PermissionDenied, NotFound) as exc:
            warn(f"Cannot create schema {catalog_name}.{schema_name}: {exc}")
            warn( "  Create it manually: CREATE SCHEMA IF NOT EXISTS {catalog_name}.{schema_name}")
            all_ok = False
        except Exception as exc:
            fail(f"Schema {catalog_name}.{schema_name}: {exc}")
            all_ok = False

    return all_ok


def setup_vector_search(endpoint_name: str, wait: bool) -> bool:
    """Create the Vector Search endpoint if it doesn't exist."""
    step("Step 5/7 — Setting up Vector Search endpoint")
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.errors import ResourceAlreadyExists
        from databricks.sdk.service.vectorsearch import EndpointType
    except ImportError:
        fail("databricks-sdk not installed.")
        return False

    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    # Check if already exists
    try:
        existing = w.vector_search_endpoints.get_endpoint(endpoint_name=endpoint_name)
        status = existing.endpoint_status.state if existing.endpoint_status else "UNKNOWN"
        if str(status) in ("ONLINE", "EndpointStatusState.ONLINE"):
            ok(f"Vector Search endpoint online: {endpoint_name}")
        else:
            warn(f"Vector Search endpoint exists but status={status}: {endpoint_name}")
            warn( "  It may still be provisioning. Check the Databricks UI.")
        return True
    except Exception:
        pass  # Does not exist — create it

    try:
        print(f"  Creating Vector Search endpoint '{endpoint_name}' (STANDARD type)...")
        w.vector_search_endpoints.create_endpoint(
            name=endpoint_name,
            endpoint_type=EndpointType.STANDARD,
        )
        ok(f"Vector Search endpoint creation started: {endpoint_name}")
    except ResourceAlreadyExists:
        ok(f"Vector Search endpoint exists: {endpoint_name}")
        return True
    except Exception as exc:
        fail(f"Vector Search endpoint creation failed: {exc}")
        return False

    if wait:
        print("  Waiting for endpoint to come online (this takes 5–15 minutes)...")
        for attempt in range(40):
            time.sleep(30)
            try:
                ep = w.vector_search_endpoints.get_endpoint(endpoint_name=endpoint_name)
                status = str(ep.endpoint_status.state) if ep.endpoint_status else ""
                if "ONLINE" in status:
                    ok(f"Vector Search endpoint is ONLINE: {endpoint_name}")
                    return True
                print(f"  ... {status} (attempt {attempt + 1}/40)")
            except Exception:
                pass
        warn(f"Timed out waiting for {endpoint_name} to become ONLINE.")
        warn( "  Check status in the Databricks UI: Catalog > Vector Search > Endpoints")
        return False
    else:
        warn("Vector Search endpoint is provisioning (typically 5–15 minutes).")
        warn(f"  Check status: Databricks UI > Catalog > Vector Search > {endpoint_name}")
        warn( "  Or re-run this script with --wait-for-vs to block until ONLINE.")
        return True


def setup_mlflow_experiments(experiment_base: str) -> bool:
    """Create MLflow experiments for dev, staging, and prod."""
    step("Step 6/7 — Setting up MLflow experiments")
    try:
        import mlflow
        from mlflow.exceptions import MlflowException
    except ImportError:
        warn("mlflow not installed — skipping experiment creation.")
        warn("  Experiments will be created automatically on first eval run.")
        return True

    mlflow.set_tracking_uri("databricks")

    all_ok = True
    for env in ("dev", "staging", "prod"):
        path = f"{experiment_base}/{env}"
        try:
            exp = mlflow.get_experiment_by_name(path)
            if exp is not None:
                ok(f"MLflow experiment exists:  {path}")
            else:
                mlflow.create_experiment(path)
                ok(f"Created MLflow experiment: {path}")
        except MlflowException as exc:
            warn(f"MLflow experiment {path}: {exc}")
            warn( "  Will be created automatically on first evaluation run.")
            all_ok = False
        except Exception as exc:
            warn(f"MLflow experiment {path}: {exc}")
            all_ok = False

    return all_ok


def run_unit_tests(skip: bool) -> bool:
    """Run unit tests as a sanity check."""
    step("Step 7/7 — Running unit tests")
    if skip:
        warn("Skipped (--skip-tests)")
        return True

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short", "-q"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode == 0:
        ok("All unit tests passed")
        return True
    else:
        fail("One or more unit tests failed — check output above.")
        fail("  Unit tests require no Databricks credentials and should always pass.")
        return False


def print_summary(env: str, dev_catalog: str, prod_catalog: str, vs_endpoint: str, success: bool) -> None:
    """Print a clear next-steps summary."""
    print(f"\n{'='*60}")
    if success:
        print(f"{BOLD}{GREEN}  AgentOps Setup Complete{RESET}")
    else:
        print(f"{BOLD}{YELLOW}  AgentOps Setup Completed with Warnings{RESET}")
    print(f"{'='*60}")
    print(f"""
  Workspace resources provisioned:
    Dev catalog:    {dev_catalog}.agentops
    Prod catalog:   {prod_catalog}.agentops
    Vector Search:  {vs_endpoint}
    MLflow:         /AgentOps/dev|staging|prod

  Next steps:
    1. Build the Python wheel:
       pip install build && python -m build

    2. Deploy to dev:
       python scripts/deploy.py --target dev

    3. Verify the deployment:
       python scripts/verify.py --target dev --test-inference

    4. Run evaluation:
       python reference_agent/eval/run_eval.py --sample 5

    5. Commit to the dev branch to trigger staging CI.

  AI coding tool setup:
    Claude Code  →  add agentops_mcp/server.py to ~/.claude/claude_desktop_config.json
    Cursor       →  open project folder; set DATABRICKS_HOST + DATABRICKS_TOKEN env vars
    Windsurf     →  open project folder; set DATABRICKS_HOST + DATABRICKS_TOKEN env vars
    Codex        →  add agentops_mcp/server.py to your Codex MCP config

  Reference: TROUBLESHOOTING.md for common failure modes.
""")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Resolve config values (prefer env vars; fall back to defaults)
    dev_catalog    = os.environ.get("AGENTOPS_DEV_CATALOG",  "agentops_dev")
    dev_schema     = os.environ.get("AGENTOPS_DEV_SCHEMA",   "agentops")
    prod_catalog   = os.environ.get("AGENTOPS_PROD_CATALOG", "agentops_prod")
    prod_schema    = os.environ.get("AGENTOPS_PROD_SCHEMA",  "agentops")
    vs_endpoint    = os.environ.get("AGENTOPS_VECTOR_SEARCH_ENDPOINT", "agentops_vs_endpoint")
    experiment_base = os.environ.get("AGENTOPS_MLFLOW_EXPERIMENT_BASE", "/AgentOps")

    print(f"\n{BOLD}AgentOps Redux — Workspace Setup{RESET}")
    print(f"Host: {os.environ.get('DATABRICKS_HOST', '<not set>')}")
    print(f"Env:  {os.environ.get('AGENTOPS_ENV', 'dev')}\n")

    results: list[bool] = []

    if not check_prerequisites():
        fail("Prerequisites not met — fix the issues above before continuing.")
        return 1

    results.append(verify_connectivity())
    results.append(install_dependencies(skip=args.skip_install))
    results.append(setup_unity_catalog(dev_catalog, dev_schema, prod_catalog, prod_schema))
    results.append(setup_vector_search(vs_endpoint, wait=args.wait_for_vs))
    results.append(setup_mlflow_experiments(experiment_base))
    results.append(run_unit_tests(skip=args.skip_tests))

    # Hard failures (False) vs warnings (None treated as ok for summary)
    success = all(r is not False for r in results)
    print_summary(
        env=os.environ.get("AGENTOPS_ENV", "dev"),
        dev_catalog=dev_catalog,
        prod_catalog=prod_catalog,
        vs_endpoint=vs_endpoint,
        success=success,
    )
    return 0 if success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time bootstrap of AgentOps workspace resources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup.py                     # full setup
  python scripts/setup.py --skip-install      # skip pip install (deps already installed)
  python scripts/setup.py --skip-tests        # skip unit tests
  python scripts/setup.py --wait-for-vs       # block until Vector Search is ONLINE
  python scripts/setup.py --skip-install --skip-tests  # fastest re-run
        """,
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip 'pip install -e .[dev]' (use if dependencies are already installed)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unit tests",
    )
    parser.add_argument(
        "--wait-for-vs",
        action="store_true",
        help="Wait (up to 20 min) for Vector Search endpoint to reach ONLINE state",
    )
    sys.exit(main(parser.parse_args()))
