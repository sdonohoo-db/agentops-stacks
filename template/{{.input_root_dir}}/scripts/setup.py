#!/usr/bin/env python3
"""
AgentOps Setup — select and install components and agent frameworks.

Presents a menu of base templates, solution patterns, and agent app examples.
Components are fetched from the agentops-stacks repo. Agent examples are fetched
from databricks/app-templates.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

APP_TEMPLATES_REPO = "databricks/app-templates"
APP_TEMPLATES_URL = f"https://github.com/{APP_TEMPLATES_REPO}.git"
APP_TEMPLATES_API = f"https://api.github.com/repos/{APP_TEMPLATES_REPO}/contents/"

PROJECT_ROOT = Path(__file__).parent.parent
COMPONENTS_DIR = PROJECT_ROOT / "components"
PREFIXES = ("agent-", "mcp-server-")

# Templates incompatible with this Python-based stacks template
EXCLUDED_TEMPLATES = {
    "agent-langchain-ts",  # TypeScript — incompatible with Python project structure
}


def fetch_template_list() -> list[dict]:
    """Get available templates with descriptions from GitHub API.
    Returns list of {"name": str, "description": str} dicts."""
    names = []
    try:
        req = urllib.request.Request(APP_TEMPLATES_API, headers={"User-Agent": "agentops-setup"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            entries = json.loads(resp.read())
        names = sorted(
            e["name"] for e in entries
            if e["type"] == "dir" and e["name"].startswith(PREFIXES)
            and e["name"] not in EXCLUDED_TEMPLATES
        )
    except Exception:
        print("GitHub API unavailable, trying git...")
        try:
            result = subprocess.run(
                ["git", "clone", "--filter=blob:none", "--bare", "--depth=1", APP_TEMPLATES_URL, "/tmp/app-templates-index"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                result = subprocess.run(
                    ["git", "-C", "/tmp/app-templates-index", "ls-tree", "--name-only", "HEAD"],
                    capture_output=True, text=True,
                )
                names = sorted(
                    n for n in result.stdout.strip().split("\n")
                    if n.startswith(PREFIXES) and n not in EXCLUDED_TEMPLATES
                )
                shutil.rmtree("/tmp/app-templates-index", ignore_errors=True)
        except Exception:
            pass

    if not names:
        return []

    # Fetch one-line descriptions from each template's README
    descriptions = _fetch_descriptions(names)
    return [{"name": n, "description": descriptions.get(n, "")} for n in names]


def _fetch_descriptions(names: list[str]) -> dict[str, str]:
    """Fetch the first meaningful line from each template's README via GitHub API."""
    descriptions = {}
    import base64
    for name in names:
        try:
            url = f"https://api.github.com/repos/{APP_TEMPLATES_REPO}/contents/{name}/README.md"
            req = urllib.request.Request(url, headers={"User-Agent": "agentops-setup"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            desc = _extract_description(content)
            if desc:
                descriptions[name] = desc
        except Exception:
            continue
    return descriptions


def _extract_description(readme: str) -> str:
    """Pull the first non-heading, non-empty line from a README as the description."""
    for line in readme.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("[") or line.startswith("!"):
            continue
        if len(line) > 70:
            line = line[:67] + "..."
        return line
    return ""


# ---------------------------------------------------------------------------
# Agent infrastructure — created when the user selects an agent template
# ---------------------------------------------------------------------------

def get_bundle_name() -> str:
    """Read the bundle name from databricks.yml."""
    bundle_yml = PROJECT_ROOT / "databricks.yml"
    if bundle_yml.exists():
        with open(bundle_yml) as f:
            for line in f:
                if line.strip().startswith("name:"):
                    return line.split(":", 1)[1].strip()
    # Fallback to pyproject.toml
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("name", "agent_project")


def to_resource_key(name: str) -> str:
    """Convert project name to a valid DAB resource key (alphanumeric + underscore)."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def install_agent_infrastructure():
    """Create the agent server scaffolding, app config, and DAB resource definitions.
    Called before installing any agent template (including empty scaffold)."""
    project_name = get_bundle_name()
    resource_key = to_resource_key(project_name)

    # agent_server/__init__.py
    agent_dir = PROJECT_ROOT / "agent_server"
    agent_dir.mkdir(exist_ok=True)
    init_py = agent_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("")

    # agent_server/start_server.py — MLflow AgentServer bootstrap
    start_server = agent_dir / "start_server.py"
    if not start_server.exists():
        start_server.write_text('''\
from pathlib import Path

from dotenv import load_dotenv
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import agent_server.agent  # noqa: E402, F401

agent_server = AgentServer("ResponsesAgent")

app = agent_server.app
setup_mlflow_git_based_version_tracking()


# Example: a test route that sends a sample request through the agent.
# The AgentServer's app is a regular FastAPI app — add routes to it
# for admin, debug, or integration test endpoints alongside your agent.
@app.get("/test")
async def test_agent():
    from agent_server.agent import handle_invoke
    from mlflow.types.responses import ResponsesAgentRequest

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "test"}],
    )
    response = await handle_invoke(request)
    return response


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")
''')
    print(f"  Created {start_server.relative_to(PROJECT_ROOT)}")

    # app.yaml — Databricks App configuration
    app_yaml = PROJECT_ROOT / "app.yaml"
    if not app_yaml.exists():
        app_yaml.write_text('''\
command: ["uv", "run", "start-server"]

env:
  - name: MLFLOW_TRACKING_URI
    value: "databricks"
  - name: MLFLOW_REGISTRY_URI
    value: "databricks-uc"
  - name: MLFLOW_EXPERIMENT_ID
    valueFrom: "experiment"
''')
    print(f"  Created app.yaml")

    # resources/app-resource.yml — Databricks App resource definition
    resources_dir = PROJECT_ROOT / "resources"
    resources_dir.mkdir(exist_ok=True)
    app_resource = resources_dir / "app-resource.yml"
    if not app_resource.exists():
        app_resource.write_text(f'''\
resources:
  apps:
    {resource_key}_agent:
      name: ${{bundle.target}}-${{var.app_name}}
      description: "${{bundle.name}} Agent App - ${{bundle.target}} environment"
      source_code_path: ../
      config:
        command: ["uv", "run", "start-server"]
        env:
          - name: MLFLOW_TRACKING_URI
            value: "databricks"
          - name: MLFLOW_REGISTRY_URI
            value: "databricks-uc"
          - name: MLFLOW_EXPERIMENT_ID
            value_from: "experiment"

      resources:
        - name: 'experiment'
          experiment:
            experiment_id: ${{resources.experiments.{resource_key}_experiment.id}}
            permission: 'CAN_MANAGE'
''')
    print(f"  Created resources/app-resource.yml")

    # Update pyproject.toml with agent dependencies and entry points
    _add_agent_deps()
    print("  Updated pyproject.toml with agent dependencies")


def _add_agent_deps():
    """Add agent-specific dependencies and entry points to pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    dest_path = PROJECT_ROOT / "pyproject.toml"
    with open(dest_path, "rb") as f:
        data = tomllib.load(f)

    # Add agent base dependencies
    agent_deps = [
        "fastapi>=0.129.0",
        "uvicorn>=0.41.0",
        "mlflow>=3.10.0",
        "databricks-agents>=1.9.3",
    ]
    existing_deps = data.get("project", {}).get("dependencies", [])
    existing_pkgs = {d.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip()
                     for d in existing_deps}
    for dep in agent_deps:
        pkg = dep.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip()
        if pkg not in existing_pkgs:
            existing_deps.append(dep)
    data.setdefault("project", {})["dependencies"] = sorted(existing_deps)

    # Add entry points
    scripts = data.setdefault("project", {}).setdefault("scripts", {})
    scripts.setdefault("start-server", "agent_server.start_server:main")

    # Add agent_server to hatch build packages
    packages = (data.get("tool", {}).get("hatch", {}).get("build", {})
                .get("targets", {}).get("wheel", {}).get("packages", []))
    if "agent_server" not in packages:
        packages.append("agent_server")
        (data.setdefault("tool", {}).setdefault("hatch", {}).setdefault("build", {})
         .setdefault("targets", {}).setdefault("wheel", {}))["packages"] = packages

    _write_toml(data, dest_path)


# ---------------------------------------------------------------------------
# Template installation
# ---------------------------------------------------------------------------

def sparse_checkout(template_name: str, dest: Path) -> bool:
    """Sparse-checkout a single template directory from the repo."""
    tmpdir = tempfile.mkdtemp(prefix="agentops-setup-")
    try:
        for url in [APP_TEMPLATES_URL, f"git@github.com:{APP_TEMPLATES_REPO}.git"]:
            result = subprocess.run(
                ["git", "clone", "--filter=blob:none", "--sparse", "--depth=1", url, tmpdir],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                break
        else:
            print(f"Failed to clone repository. Download manually from:")
            print(f"  https://github.com/{APP_TEMPLATES_REPO}/tree/main/{template_name}")
            return False

        subprocess.run(
            ["git", "-C", tmpdir, "sparse-checkout", "set", template_name],
            check=True, capture_output=True, text=True,
        )

        src = Path(tmpdir) / template_name
        if not src.exists():
            print(f"Template '{template_name}' not found in repository.")
            return False

        # Copy agent_server/ if it exists (agent templates)
        agent_src = src / "agent_server"
        if agent_src.exists():
            agent_dest = dest / "agent_server"
            agent_dest.mkdir(exist_ok=True)
            for item in agent_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, agent_dest / item.name)

        # Copy scripts/ if they exist
        scripts_src = src / "scripts"
        if scripts_src.exists():
            scripts_dest = dest / "scripts"
            scripts_dest.mkdir(exist_ok=True)
            for item in scripts_src.iterdir():
                if item.name == "setup.py":
                    continue  # don't overwrite our setup script
                shutil.copy2(item, scripts_dest / item.name)

        # Copy app.yaml if present (may have template-specific env vars)
        app_yaml = src / "app.yaml"
        if app_yaml.exists():
            shutil.copy2(app_yaml, dest / "app.yaml")

        # Merge framework-specific deps into our pyproject.toml
        pyproject = src / "pyproject.toml"
        if pyproject.exists():
            merge_pyproject(pyproject, dest / "pyproject.toml")

        # Copy .env.example if present
        env_example = src / ".env.example"
        if env_example.exists():
            shutil.copy2(env_example, dest / ".env.example")

        return True

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def merge_pyproject(src_path: Path, dest_path: Path):
    """Merge template pyproject.toml dependencies into ours, preserving our
    project metadata, entry points, and build config."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # Python < 3.11

    with open(src_path, "rb") as f:
        src = tomllib.load(f)
    with open(dest_path, "rb") as f:
        dest = tomllib.load(f)

    # Merge dependencies — union of both, template version specs win on conflict
    our_deps = {d.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip(): d
                for d in dest.get("project", {}).get("dependencies", [])}
    for dep in src.get("project", {}).get("dependencies", []):
        pkg = dep.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip()
        our_deps[pkg] = dep  # template version wins
    dest.setdefault("project", {})["dependencies"] = sorted(our_deps.values())

    # Merge entry points from template (add new ones, don't remove ours)
    src_scripts = src.get("project", {}).get("scripts", {})
    dest.setdefault("project", {}).setdefault("scripts", {})
    for name, target in src_scripts.items():
        if name not in dest["project"]["scripts"]:
            dest["project"]["scripts"][name] = target

    # Merge dependency-groups (dev, setup, etc.)
    for group, deps in src.get("dependency-groups", {}).items():
        existing = dest.setdefault("dependency-groups", {}).get(group, [])
        existing_pkgs = {d.split(">")[0].split("=")[0].strip() for d in existing}
        for dep in deps:
            pkg = dep.split(">")[0].split("=")[0].strip()
            if pkg not in existing_pkgs:
                existing.append(dep)
        dest.setdefault("dependency-groups", {})[group] = existing

    # Merge tool.uv settings
    if "tool" in src and "uv" in src["tool"]:
        dest.setdefault("tool", {}).setdefault("uv", {}).update(src["tool"]["uv"])

    _write_toml(dest, dest_path)


def _write_toml(data: dict, path: Path):
    """Simple TOML writer — handles the subset we need (no datetime, etc.)."""
    lines = []

    def write_value(v):
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            items = ", ".join(write_value(i) for i in v)
            if len(items) > 80:
                inner = ",\n".join(f"    {write_value(i)}" for i in v)
                return f"[\n{inner},\n]"
            return f"[{items}]"
        if isinstance(v, dict):
            items = ", ".join(f"{k} = {write_value(val)}" for k, val in v.items())
            return "{" + f" {items} " + "}"
        return str(v)

    def write_section(d, prefix=""):
        for key, val in d.items():
            if isinstance(val, dict) and not all(isinstance(v, str) for v in val.values()):
                section = f"{prefix}.{key}" if prefix else key
                leaves = {k: v for k, v in val.items() if not isinstance(v, dict)}
                tables = {k: v for k, v in val.items() if isinstance(v, dict)}
                if leaves or not tables:
                    lines.append(f"\n[{section}]")
                    for lk, lv in leaves.items():
                        lines.append(f"{lk} = {write_value(lv)}")
                for tk, tv in tables.items():
                    write_section({tk: tv}, prefix=section)
            elif isinstance(val, dict):
                section = f"{prefix}.{key}" if prefix else key
                lines.append(f"\n[{section}]")
                for k2, v2 in val.items():
                    lines.append(f"{k2} = {write_value(v2)}")
            else:
                lines.append(f"{key} = {write_value(val)}")

    write_section(data)
    path.write_text("\n".join(lines).strip() + "\n")


# ---------------------------------------------------------------------------
# Component installation
# ---------------------------------------------------------------------------

def parse_component_manifest(component_dir: Path) -> dict:
    """Parse the YAML frontmatter from a component's component.md."""
    if yaml is None:
        print("ERROR: PyYAML is required for component installation.")
        print("  Run 'uv sync' first, then 'uv run setup'.")
        sys.exit(1)

    manifest_path = component_dir / "component.md"
    content = manifest_path.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid manifest: no YAML frontmatter in {manifest_path}")
    return yaml.safe_load(parts[1])


def resolve_component_deps(component_names: list[str], components_dir: Path) -> list[str]:
    """Resolve dependencies and return component names in topological install order."""
    manifests = {}
    to_process = list(component_names)
    while to_process:
        name = to_process.pop(0)
        if name in manifests:
            continue
        comp_dir = components_dir / name
        if not comp_dir.exists():
            raise FileNotFoundError(f"Component '{name}' not found in {components_dir}")
        manifests[name] = parse_component_manifest(comp_dir)
        for dep in manifests[name].get("requires", []):
            if dep not in manifests:
                to_process.append(dep)

    # Topological sort — dependencies before dependents
    ordered = []
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        for dep in manifests[name].get("requires", []):
            visit(dep)
        ordered.append(name)

    for name in manifests:
        visit(name)
    return ordered



def fetch_external_source(source: dict, dest_root: Path) -> bool:
    """Fetch an external source via sparse checkout (e.g., from databricks/app-templates)."""
    repo = source["repo"]
    src_path = source["path"]
    dest_path = dest_root / source["dest"]

    if dest_path.exists():
        return True

    tmpdir = tempfile.mkdtemp(prefix="agentops-external-")
    try:
        for url in [f"https://github.com/{repo}.git", f"git@github.com:{repo}.git"]:
            result = subprocess.run(
                ["git", "clone", "--filter=blob:none", "--sparse", "--depth=1", url, tmpdir],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                break
        else:
            print(f"  WARNING: Could not clone {repo} — skipping {src_path}")
            return False

        subprocess.run(
            ["git", "-C", tmpdir, "sparse-checkout", "set", src_path],
            check=True, capture_output=True, text=True,
        )

        src = Path(tmpdir) / src_path
        if not src.exists():
            print(f"  WARNING: {src_path} not found in {repo}")
            return False

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest_path)
        else:
            shutil.copy2(src, dest_path)
        print(f"  Fetched {src_path}")

        # Remove standalone artifacts that conflict with the parent bundle
        for item_name in source.get("remove_after_fetch", []):
            item_path = dest_path / item_name
            if item_path.is_dir():
                shutil.rmtree(item_path)
            elif item_path.is_file():
                item_path.unlink()

        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def copy_component_files(manifest: dict, component_dir: Path, project_root: Path):
    """Copy files declared in the manifest's copies section."""
    for entry in manifest.get("copies", []):
        src = component_dir / entry["src"]
        dest = project_root / entry["dest"]

        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
            print(f"  Copied {entry['src']} → {entry['dest']}")
        elif src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  Copied {entry['dest']}")


def apply_modifications(manifest: dict, project_root: Path):
    """Apply all modifications declared in the manifest."""
    for mod in manifest.get("modifies", []):
        target = project_root / mod["target"]
        action = mod["action"]
        if action == "append_list":
            _mod_append_list(target, mod["path"], mod["values"])
        elif action == "add_dependencies":
            _mod_add_dependencies(target, mod["values"])
        elif action == "add_entry_points":
            _mod_add_entry_points(target, mod["values"])
        elif action == "set_command":
            _mod_set_command(target, mod["value"])
        elif action == "merge_env":
            _mod_merge_env(target, mod["values"])
        else:
            print(f"  WARNING: Unknown modification action '{action}' in manifest")


def _mod_append_list(target: Path, yaml_path: str, values: list[str]):
    """Append values to a YAML list (e.g., sync.include in databricks.yml).
    Uses text-based editing to preserve DAB variable syntax."""
    if not target.exists():
        print(f"  WARNING: {target.name} not found, skipping append_list")
        return

    content = target.read_text()
    lines = content.splitlines(keepends=True)
    keys = yaml_path.split(".")

    # Collect existing list values for dedup
    existing_vals = set()
    for line in lines:
        s = line.strip()
        if s.startswith("- "):
            existing_vals.add(s[2:].strip().strip('"').strip("'"))

    new_values = [v for v in values if v not in existing_vals]
    if not new_values:
        return

    # Find the list: <keys[0]>: then <keys[1]>: under it, then list items
    in_parent = False
    in_list = False
    insert_pos = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Match top-level parent key
        if not line[0:1].isspace() and stripped.startswith(f"{keys[0]}:"):
            in_parent = True
            continue

        # Match nested list key under parent
        if in_parent and len(keys) > 1 and stripped.startswith(f"{keys[-1]}:"):
            in_list = True
            continue

        if in_list:
            if stripped.startswith("- "):
                insert_pos = i
            elif stripped:
                break

        # Reset if we hit another top-level key
        if not line[0:1].isspace() and ":" in stripped:
            if in_parent and not in_list:
                in_parent = False

    if insert_pos is not None:
        # Match indent of existing list items
        ref_line = lines[insert_pos]
        indent = ref_line[: len(ref_line) - len(ref_line.lstrip())]
        additions = [f'{indent}- "{v}"\n' for v in new_values]
        lines = lines[: insert_pos + 1] + additions + lines[insert_pos + 1 :]
        target.write_text("".join(lines))
        print(f"  Updated {target.name}: appended to {yaml_path}")
    else:
        print(f"  WARNING: Could not find {yaml_path} in {target.name}")


def _mod_add_dependencies(target: Path, values: list[str]):
    """Add dependencies to pyproject.toml [project.dependencies]."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(target, "rb") as f:
        data = tomllib.load(f)

    existing = data.get("project", {}).get("dependencies", [])
    existing_pkgs = {
        d.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip() for d in existing
    }
    added = []
    for dep in values:
        pkg = dep.split(">")[0].split("=")[0].split("[")[0].split("<")[0].strip()
        if pkg not in existing_pkgs:
            existing.append(dep)
            added.append(pkg)

    if added:
        data.setdefault("project", {})["dependencies"] = sorted(existing)
        _write_toml(data, target)
        print(f"  Updated pyproject.toml: added deps {', '.join(added)}")


def _mod_add_entry_points(target: Path, values: dict):
    """Add entry points to pyproject.toml [project.scripts]."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(target, "rb") as f:
        data = tomllib.load(f)

    scripts = data.setdefault("project", {}).setdefault("scripts", {})
    added = []
    for name, entry_point in values.items():
        if name not in scripts:
            scripts[name] = entry_point
            added.append(name)

    if added:
        _write_toml(data, target)
        print(f"  Updated pyproject.toml: added scripts {', '.join(added)}")


def _mod_set_command(target: Path, value):
    """Replace the command: field in an app.yaml or resource YAML file."""
    if not target.exists():
        print(f"  WARNING: {target.name} not found, skipping set_command")
        return

    content = target.read_text()
    cmd_json = json.dumps(value)
    new_lines = []
    changed = False
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("command:"):
            indent = line[: len(line) - len(stripped)]
            new_lines.append(f"{indent}command: {cmd_json}\n")
            changed = True
        else:
            new_lines.append(line)

    if changed:
        target.write_text("".join(new_lines))
        print(f"  Updated {target.name}: set command to {cmd_json}")


def _mod_merge_env(target: Path, values: list[dict]):
    """Merge env vars into an env: list in a YAML file (app.yaml or resource yml)."""
    if not target.exists():
        print(f"  WARNING: {target.name} not found, skipping merge_env")
        return

    content = target.read_text()
    lines = content.splitlines(keepends=True)

    # Existing env var names
    existing_names = set()
    for line in lines:
        s = line.strip()
        if s.startswith("- name:"):
            existing_names.add(s.split(":", 1)[1].strip().strip('"'))

    new_vars = [v for v in values if v["name"] not in existing_names]
    if not new_vars:
        return

    # Find the last env entry to insert after
    last_env_idx = None
    env_item_indent = ""
    in_env = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("env:"):
            in_env = True
            continue
        if in_env:
            if stripped.startswith("- name:"):
                env_item_indent = line[: len(line) - len(line.lstrip())]
                last_env_idx = i
                # value/value_from/valueFrom on the next line
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("value"):
                    last_env_idx = i + 1
            elif stripped and not stripped.startswith("value") and not stripped.startswith("#"):
                in_env = False

    if last_env_idx is not None:
        additions = []
        for var in new_vars:
            additions.append(f"{env_item_indent}- name: {var['name']}\n")
            additions.append(f"{env_item_indent}  value: \"{var['value']}\"\n")
        lines = lines[: last_env_idx + 1] + additions + lines[last_env_idx + 1 :]
        target.write_text("".join(lines))
        names = [v["name"] for v in new_vars]
        print(f"  Updated {target.name}: added env vars {', '.join(names)}")


def replace_instance_names(project_root: Path, resource_key: str):
    """Replace INSTANCE_NAME / INSTANCE_DASH_NAME placeholders in resource files."""
    dash_name = resource_key.replace("_", "-")
    for yml_file in (project_root / "resources").glob("*.yml"):
        content = yml_file.read_text()
        if "INSTANCE_NAME" in content or "INSTANCE_DASH_NAME" in content:
            content = content.replace("INSTANCE_DASH_NAME", dash_name)
            content = content.replace("INSTANCE_NAME", resource_key)
            yml_file.write_text(content)
            print(f"  Updated {yml_file.name}: replaced instance name placeholders")


def _add_hatch_packages(project_root: Path, packages: list[str]):
    """Add top-level directories to hatch build packages in pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    target = project_root / "pyproject.toml"
    with open(target, "rb") as f:
        data = tomllib.load(f)

    existing = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    added = []
    for pkg in packages:
        if pkg not in existing:
            existing.append(pkg)
            added.append(pkg)

    if added:
        (
            data.setdefault("tool", {})
            .setdefault("hatch", {})
            .setdefault("build", {})
            .setdefault("targets", {})
            .setdefault("wheel", {})
        )["packages"] = existing
        _write_toml(data, target)
        print(f"  Updated pyproject.toml: added build packages {', '.join(added)}")


def install_components(component_names: list[str]):
    """Install components from the local components/ directory, copying files
    and applying declared modifications."""
    if not COMPONENTS_DIR.exists():
        print(f"\n  ERROR: Components directory not found at {COMPONENTS_DIR}")
        print("  Re-run 'databricks bundle init' to regenerate the project.")
        sys.exit(1)

    project_name = get_bundle_name()
    resource_key = to_resource_key(project_name)

    # Resolve dependencies and determine install order
    ordered = resolve_component_deps(component_names, COMPONENTS_DIR)
    print(f"\n  Components to install: {', '.join(ordered)}\n")

    for name in ordered:
        comp_dir = COMPONENTS_DIR / name
        manifest = parse_component_manifest(comp_dir)

        print(f"  [{name}]")

        # Copy declared files from component into project
        copy_component_files(manifest, comp_dir, PROJECT_ROOT)

        # Fetch external sources declared by the component
        for source in manifest.get("external_sources", []):
            print(f"  Fetching {source['path']} from {source['repo']}...")
            fetch_external_source(source, PROJECT_ROOT)

        # Apply declared modifications to existing project files
        apply_modifications(manifest, PROJECT_ROOT)

        # Add top-level directories to hatch build packages
        hatch_pkgs = []
        for entry in manifest.get("copies", []):
            dest = entry["dest"].rstrip("/")
            if "/" not in dest and (PROJECT_ROOT / dest).is_dir():
                hatch_pkgs.append(dest)
        if hatch_pkgs:
            _add_hatch_packages(PROJECT_ROOT, hatch_pkgs)

        print()

    # Replace INSTANCE_NAME placeholders with the project's resource key
    replace_instance_names(PROJECT_ROOT, resource_key)

    # Clean up components directory — no longer needed after installation
    if COMPONENTS_DIR.exists():
        shutil.rmtree(COMPONENTS_DIR)
        print("  Cleaned up components/")


# ---------------------------------------------------------------------------
# Menu and resource tags
# ---------------------------------------------------------------------------

# Resource requirement tags for templates that need external resources
RESOURCE_TAGS = {
    "agent-langgraph-advanced": "[requires Lakebase]",
    "agent-openai-advanced": "[requires Lakebase]",
    "agent-openai-agents-sdk-multiagent": "[requires Genie Space + Serving Endpoints]",
    "mcp-server-open-api-spec": "[requires UC Connection + Volume]",
}

# Templates that need Lakebase
LAKEBASE_TEMPLATES = {
    "agent-langgraph-advanced",
    "agent-openai-advanced",
}

# Solution pattern templates (future — not yet available)
SOLUTION_PATTERNS = [
    {"name": "RAG agent", "tag": "[requires Vector Search + UC Volume]"},
    {"name": "Document Intelligence agent", "tag": "[requires UC Volume]"},
    {"name": "RPA / Process Automation agent", "tag": "[requires Lakebase + API connections]"},
]


def build_menu(templates: list[dict]) -> list[dict]:
    """Organize templates into grouped menu entries."""
    menu = []

    # --- Base Templates ---
    menu.append({"name": "Empty DAB (no components)", "group": "Base Templates",
                 "selectable": True, "action": "empty_dab"})
    menu.append({"name": "Single Agent (Databricks App)", "group": "Base Templates",
                 "selectable": True, "action": "single_agent"})
    menu.append({"name": "Single MCP Server", "group": "Base Templates",
                 "selectable": True, "action": "mcp_server"})

    # --- Solution Patterns ---
    for sp in SOLUTION_PATTERNS:
        menu.append({"name": sp["name"], "group": "Solution Patterns",
                     "selectable": False, "action": "future", "tag": sp["tag"] + " (Coming soon)"})

    # --- Agent App Examples (from databricks/app-templates) ---
    agents_simple = [t for t in templates
                     if t["name"].startswith("agent-") and t["name"] not in LAKEBASE_TEMPLATES]
    agents_memory = [t for t in templates
                     if t["name"] in LAKEBASE_TEMPLATES]
    mcp_servers = [t for t in templates
                   if t["name"].startswith("mcp-server-")]

    for t in agents_simple + agents_memory + mcp_servers:
        tag = RESOURCE_TAGS.get(t["name"], "")
        if tag:
            tag = f"{tag} (Coming soon)"
        else:
            tag = "(Coming soon)"
        menu.append({"name": t["name"], "group": "Agent App Examples",
                     "selectable": False, "action": "install", "tag": tag,
                     "description": t.get("description", "")})

    return menu


def print_menu(menu: list[dict]) -> None:
    """Print the grouped menu with numbered entries."""
    max_name = max(len(e["name"]) for e in menu)
    current_group = None
    idx = 1

    for entry in menu:
        if entry["group"] != current_group:
            current_group = entry["group"]
            print(f"\n  {current_group}")

        tag = f"  {entry.get('tag', '')}" if entry.get("tag") else ""
        desc = f"  — {entry['description']}" if entry.get("description") else ""

        if entry["selectable"]:
            print(f"    {idx:2d}) {entry['name']:<{max_name}}{tag}{desc}")
            idx += 1
        else:
            print(f"     -  {entry['name']:<{max_name}}{tag}")

    print(f"\n     0) Exit")
    return idx - 1  # total selectable count


def install_empty_scaffold():
    """Generate a minimal working agent locally without pulling from app-templates."""
    agent_dir = PROJECT_ROOT / "agent_server"
    agent_dir.mkdir(exist_ok=True)

    # Minimal agent.py with @invoke/@stream contract
    agent_py = agent_dir / "agent.py"
    if not agent_py.exists() or agent_py.read_text().strip().startswith("raise NotImplementedError"):
        agent_py.write_text('''\
"""Minimal agent scaffold — edit this file to add your agent logic.

Define agent logic as standalone async functions, then register them with
invoke() and stream(). Keeping the logic separate means it's callable
from custom routes — see the /test route in start_server.py.
"""

import logging
from datetime import datetime
from typing import AsyncGenerator

from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    create_text_delta,
)

logger = logging.getLogger(__name__)


async def handle_stream(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Stream a response. Replace this with your agent logic."""
    item_id = "msg_001"
    text = f"Agent scaffold is running. Current time: {datetime.now().isoformat()}"
    yield create_text_delta(text, item_id)


async def handle_invoke(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Handle a single request. Replace this with your agent logic."""
    outputs = [
        event.item
        async for event in handle_stream(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs)


# Register handlers with the AgentServer.
invoke()(handle_invoke)
stream()(handle_stream)
''')
    print(f"  Created {agent_py.relative_to(PROJECT_ROOT)}")

    # Minimal utils.py
    utils_py = agent_dir / "utils.py"
    if not utils_py.exists():
        utils_py.write_text('''\
"""Shared utilities for the agent server."""

from databricks.sdk import WorkspaceClient
from mlflow.genai.agent_server import get_request_headers
from mlflow.types.responses import ResponsesAgentRequest


def get_session_id(request: ResponsesAgentRequest) -> str | None:
    if request.context and request.context.conversation_id:
        return request.context.conversation_id
    if request.custom_inputs and isinstance(request.custom_inputs, dict):
        return request.custom_inputs.get("session_id")
    return None


def get_user_workspace_client() -> WorkspaceClient:
    token = get_request_headers().get("x-forwarded-access-token")
    return WorkspaceClient(token=token, auth_type="pat")
''')
    print(f"  Created {utils_py.relative_to(PROJECT_ROOT)}")


def main():
    print("AgentOps Setup")
    print("=" * 50)
    print(f"Fetching available templates from {APP_TEMPLATES_REPO}...\n")

    templates = fetch_template_list()
    if not templates:
        print("Could not fetch template list. Check your network connection.")
        print(f"You can browse templates at: https://github.com/{APP_TEMPLATES_REPO}")

    menu = build_menu(templates)
    selectable = [e for e in menu if e["selectable"]]
    max_choice = print_menu(menu)

    while True:
        try:
            choice = input(f"\nSelect a template [1-{max_choice}, 0 to exit]: ").strip()
            if choice == "0":
                print("\nExiting. Run 'uv run setup' again when ready.")
                return
            num = int(choice)
            if 1 <= num <= max_choice:
                break
        except (ValueError, EOFError):
            pass
        print("Invalid selection, try again.")

    selected = selectable[num - 1]

    # Empty DAB — nothing to install, just confirm
    if selected["action"] == "empty_dab":
        print("\nEmpty DAB scaffold ready.")
        print("\nNext steps:")
        print("  1. Set workspace URLs in databricks.yml targets")
        print("  2. Add components to resources/ as needed")
        print("  3. Run 'databricks bundle validate' to check config")
        print("  4. Run 'databricks bundle deploy -t dev' to deploy")
        return

    # Component-based templates
    if selected["action"] == "single_agent":
        install_components(["agent_app"])
        print("Single Agent installed.")
        print("\nNext steps:")
        print("  1. Edit agent_server/agent.py with your agent logic")
        print("  2. To test locally: uv sync && uv run start-server")
        print("  3. Run 'databricks bundle deploy -t dev' to deploy")
        return

    if selected["action"] == "mcp_server":
        install_components(["mcp_server"])
        print("Single MCP Server installed.")
        print("\nNext steps:")
        print("  1. Add your tools in server/tools.py")
        print("  2. To test locally: uv sync && uv run custom-mcp-server")
        print("  3. Run 'databricks bundle deploy -t dev' to deploy")
        return

    # Agent templates — set up agent infrastructure first
    if selected["action"] in ("empty_scaffold", "install"):
        is_agent = (selected["action"] == "empty_scaffold"
                    or selected.get("name", "").startswith("agent-"))
        if is_agent:
            print("\nSetting up agent infrastructure...")
            install_agent_infrastructure()

    if selected["action"] == "empty_scaffold":
        install_empty_scaffold()
        print("\nEmpty Agent Scaffold installed.")
        print("\nNext steps:")
        print("  1. Edit agent_server/agent.py with your agent logic")
        print("  2. To test locally: uv sync && uv run start-server")
        print("  3. Run 'databricks bundle deploy -t dev' to deploy")
        return

    template_name = selected["name"]
    print(f"\nInstalling '{template_name}'...")

    tag = RESOURCE_TAGS.get(template_name, "")
    if tag:
        print(f"\n  Note: This template {tag.lower()}")
        print("  See the project README for setup instructions.\n")

    # For MCP servers, ensure agent_server/ dir exists (sparse_checkout copies into it)
    if template_name.startswith("mcp-server-"):
        (PROJECT_ROOT / "agent_server").mkdir(exist_ok=True)
        (PROJECT_ROOT / "agent_server" / "__init__.py").touch()

    if sparse_checkout(template_name, PROJECT_ROOT):
        print(f"\nInstalled '{template_name}' into project.")
        print("\nNext steps:")
        if template_name.startswith("agent-"):
            print("  1. Review agent_server/agent.py and configure your agent")
            print("  2. To test locally: uv sync && uv run start-server")
        else:
            print("  1. Review the installed files and configure as needed")
            print("  2. To test locally: uv sync")
        print("  3. Run 'databricks bundle deploy -t dev' to deploy")
    else:
        print("\nSetup failed. See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
