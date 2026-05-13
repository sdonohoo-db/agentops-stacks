# Databricks notebook source
# MAGIC %md
# MAGIC # Install agentops-stacks Skill for Genie Code
# MAGIC
# MAGIC Uploads the agentops-stacks skill (SKILL.md, render.py, schema, and the
# MAGIC bundled template tree) to your workspace so Genie Code can use it to
# MAGIC scaffold new DAB projects.
# MAGIC
# MAGIC Destination: `/Workspace/Users/<your_username>/.assistant/skills/agentops-stacks/`
# MAGIC
# MAGIC **How to use:** Run all cells top to bottom. Edit the GITHUB_REF below
# MAGIC if you want to install from a branch other than the default.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# -- Configuration ----------------------------------------------------------
# Source repo and ref. Currently published from the sdonohoo-db fork; will
# move to databricks-solutions/agentops-stacks once stabilized.
GITHUB_OWNER = "sdonohoo-db"
GITHUB_REPO = "agentops-stacks"
GITHUB_REF = "main"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install

# COMMAND ----------

import base64
import json
import posixpath
import urllib.request

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat


def _github_api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  WARN GitHub API error: {e}")
        return None


def _download(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except Exception:
        return None


def _upload(w, workspace_path, content):
    w.workspace.mkdirs(posixpath.dirname(workspace_path))
    w.workspace.import_(
        path=workspace_path,
        content=base64.b64encode(content).decode(),
        format=ImportFormat.AUTO,
        overwrite=True,
    )


def _list_repo_paths(owner, repo, ref, path_prefixes):
    """Return blob paths under any of `path_prefixes` from the repo's git tree."""
    data = _github_api(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
    )
    if data is None:
        return []
    out = []
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue
        p = item["path"]
        if any(p == prefix or p.startswith(prefix + "/") for prefix in path_prefixes):
            out.append(p)
    return out


# ── Main ───────────────────────────────────────────────────────────────────

w = WorkspaceClient()
username = w.current_user.me().user_name
skills_path = f"/Users/{username}/.assistant/skills"
skill_dest = f"{skills_path}/agentops-stacks"

print(f"Username:  {username}")
print(f"Source:    github.com/{GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_REF}")
print(f"Target:    {skill_dest}")
print()

# Paths to bundle into the workspace skill directory.
# - SKILL.md and render.py: the skill itself.
# - databricks_template_schema.json: input definitions and defaults.
# - template/ and library/: the canonical template tree, copied alongside the
#   skill so the renderer is self-contained in the workspace.
SKILL_BASE = "plugin/skills/agentops-stacks"
REPO_BUNDLES = {
    f"{SKILL_BASE}/SKILL.md": "SKILL.md",
    f"{SKILL_BASE}/render.py": "render.py",
    "databricks_template_schema.json": "databricks_template_schema.json",
}
REPO_TREES = {
    "template": "template",
    "library": "library",
}

raw_base = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_REF}"

print("Discovering files in source repo...")
tree_prefixes = list(REPO_TREES.keys())
tree_paths = _list_repo_paths(GITHUB_OWNER, GITHUB_REPO, GITHUB_REF, tree_prefixes)
print(f"  Discovered {len(tree_paths)} files in {tree_prefixes}\n")

w.workspace.mkdirs(skill_dest)

uploaded = 0
failed = 0

print("Uploading skill files...")
for src_path, dest_name in REPO_BUNDLES.items():
    data = _download(f"{raw_base}/{src_path}")
    if data is None:
        print(f"  FAIL {dest_name}")
        failed += 1
        continue
    _upload(w, f"{skill_dest}/{dest_name}", data)
    uploaded += 1
    print(f"  OK   {dest_name}")

print()
print("Uploading bundled template + library...")
for src_path in tree_paths:
    # Map repo path → workspace path under the skill directory.
    for src_prefix, dest_prefix in REPO_TREES.items():
        if src_path == src_prefix or src_path.startswith(src_prefix + "/"):
            rel = src_path[len(src_prefix) :].lstrip("/")
            dest = f"{skill_dest}/{dest_prefix}" + (f"/{rel}" if rel else "")
            break
    else:
        continue
    data = _download(f"{raw_base}/{src_path}")
    if data is None:
        print(f"  FAIL {src_path}")
        failed += 1
        continue
    _upload(w, dest, data)
    uploaded += 1

print()
print(f"Done. {uploaded} files uploaded, {failed} failed.")
print(f"Skill is at: /Workspace{skill_dest}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Installation

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
username = w.current_user.me().user_name
skills_path = f"/Users/{username}/.assistant/skills/agentops-stacks"

try:
    entries = list(w.workspace.list(skills_path))
    print(f"Top-level entries under {skills_path}:\n")
    for e in sorted(entries, key=lambda x: x.path):
        kind = "DIR " if str(e.object_type) == "ObjectType.DIRECTORY" else "FILE"
        print(f"  {kind}  {e.path.split('/')[-1]}")
except Exception as e:
    print(f"Could not list skill directory: {e}")
