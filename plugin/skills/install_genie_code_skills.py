# Databricks notebook source
# MAGIC %md
# MAGIC # Install agentops-stacks Skill for Genie Code
# MAGIC
# MAGIC Uploads the agentops-stacks SKILL.md to your workspace so Genie Code
# MAGIC can use it to scaffold new DAB projects via `databricks bundle init`.
# MAGIC
# MAGIC Destination: `/Workspace/Users/<your_username>/.assistant/skills/agentops-stacks/SKILL.md`
# MAGIC
# MAGIC **Prereqs in your workspace:** the Databricks CLI (already present in
# MAGIC Genie Code) and the ai-dev-kit plugin skills installed under
# MAGIC `/Workspace/Users/<you>/.assistant/skills/` for post-scaffold work.
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
#
# GITHUB_REF defaults to "main" and can be overridden via the
# AGENTOPS_GITHUB_REF env var when running this file as a regular Python
# script (useful for testing branches before merging).
import os

GITHUB_OWNER = "sdonohoo-db"
GITHUB_REPO = "agentops-stacks"
GITHUB_REF = os.environ.get("AGENTOPS_GITHUB_REF", "main")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install

# COMMAND ----------

import base64
import posixpath
import urllib.request

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat


def _download(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"  download error: {e}")
        return None


def _upload(w, workspace_path, content):
    w.workspace.mkdirs(posixpath.dirname(workspace_path))
    w.workspace.import_(
        path=workspace_path,
        content=base64.b64encode(content).decode(),
        format=ImportFormat.AUTO,
        overwrite=True,
    )


# ── Main ───────────────────────────────────────────────────────────────────

w = WorkspaceClient()
username = w.current_user.me().user_name
skill_dest = f"/Users/{username}/.assistant/skills/agentops-stacks"

print(f"Username: {username}")
print(f"Source:   github.com/{GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_REF}")
print(f"Target:   {skill_dest}/SKILL.md")
print()

# The skill is a single SKILL.md file. `databricks bundle init` pulls the
# template tree, library, and schema directly from the GitHub repo at run
# time — no need to vendor them next to the skill in the workspace.
src_url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_REF}/plugin/skills/agentops-stacks/SKILL.md"

print("Downloading SKILL.md...")
data = _download(src_url)
if data is None:
    raise RuntimeError(f"Could not download {src_url}")

print("Uploading to workspace...")
_upload(w, f"{skill_dest}/SKILL.md", data)
print(f"  OK  {skill_dest}/SKILL.md")
print()
print(f"Done. Skill is at: /Workspace{skill_dest}/SKILL.md")

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
    print(f"Entries under {skills_path}:\n")
    for e in sorted(entries, key=lambda x: x.path):
        kind = "DIR " if str(e.object_type) == "ObjectType.DIRECTORY" else "FILE"
        print(f"  {kind}  {e.path.split('/')[-1]}")
except Exception as e:
    print(f"Could not list skill directory: {e}")
