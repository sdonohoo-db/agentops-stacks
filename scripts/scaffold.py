"""
Agent Scaffolding Script
=========================
Create a new agent project from templates, wired into the AgentOps
framework with all the right boilerplate.

Usage:
    python scripts/scaffold.py --name my_agent --description "My custom agent"
    python scripts/scaffold.py --name my_agent --type rag
    python scripts/scaffold.py --name my_agent --type summarization

What this script creates:
    reference_agent/agents/<name>/
        agent.py   - Agent implementation extending AgentBase
        tools.py   - UC tool registration for this agent
    reference_agent/eval/eval_<name>.jsonl  - Starter eval dataset
    bundle/resources/<name>_workflow.yml    - DAB workflow for this agent

After scaffolding:
    1. Implement the _invoke() method in agent.py
    2. Define your tools in tools.py
    3. Register the agent in reference_agent/router/router.py
    4. Add eval samples to eval_<name>.jsonl
    5. Run: python scripts/deploy.py --target dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_ROOT = PROJECT_ROOT / "templates"

# Starter eval dataset written by scaffold.py.
# These two questions are intentional placeholders that run immediately so the eval gate
# does not hard-fail on an empty file.  Replace them (and add more) with domain-specific
# questions and expected responses before promoting to staging.
# The "scaffold_placeholder": true metadata flag identifies entries that still need updating.
EVAL_DATASET_TEMPLATE = (
    '{"request": "What is the main purpose of this agent and what kinds of questions can it answer?",'
    ' "expected_response": "This agent is designed to answer questions and assist users with tasks in its domain.'
    ' Replace this expected response with a description of what your specific agent does and handles.",'
    ' "metadata": {"category": "general", "difficulty": "easy", "scaffold_placeholder": true}}\n'
    '{"request": "How should I phrase my question to get the best results from this agent?",'
    ' "expected_response": "Provide clear, specific questions with relevant context.'
    ' The agent works best with well-defined queries about its domain.'
    ' Replace this expected response with guidance specific to your agent.",'
    ' "metadata": {"category": "general", "difficulty": "easy", "scaffold_placeholder": true}}\n'
)


def _load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def scaffold_agent(
    agent_name: str,
    description: str,
    agent_type: str = "generic",
) -> None:
    """Create scaffolded files for a new agent."""
    agent_dir = PROJECT_ROOT / "reference_agent" / "agents" / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    class_name = "".join(word.capitalize() for word in agent_name.split("_")) + "Agent"
    name_title = agent_name.replace("_", " ").title()

    # Write agent.py from template
    agent_tmpl = _load_template(TEMPLATES_ROOT / "agent" / "agent.py.tmpl")
    agent_content = agent_tmpl.format(
        agent_name_title=name_title,
        title_underline="=" * (len(name_title) + 6),
        description=description,
        class_name=class_name,
        agent_name=agent_name,
    )
    (agent_dir / "agent.py").write_text(agent_content)
    print(f"  Created: reference_agent/agents/{agent_name}/agent.py")

    # Write tools.py from template
    tools_tmpl = _load_template(TEMPLATES_ROOT / "agent" / "tools.py.tmpl")
    tools_content = tools_tmpl.format(
        agent_name_title=name_title,
        agent_name=agent_name,
    )
    (agent_dir / "tools.py").write_text(tools_content)
    print(f"  Created: reference_agent/agents/{agent_name}/tools.py")

    # Write __init__.py
    (agent_dir / "__init__.py").write_text("")

    # Write eval dataset
    eval_path = PROJECT_ROOT / "reference_agent" / "eval" / f"eval_{agent_name}.jsonl"
    eval_path.write_text(EVAL_DATASET_TEMPLATE)
    print(f"  Created: reference_agent/eval/eval_{agent_name}.jsonl")

    # Write DAB workflow from template
    workflow_tmpl = _load_template(TEMPLATES_ROOT / "workflow" / "agent_workflow.yml.tmpl")
    workflow_content = workflow_tmpl.format(
        agent_name_title=name_title,
        agent_name=agent_name,
        description=description,
    )
    workflow_path = PROJECT_ROOT / "bundle" / "resources" / f"{agent_name}_workflow.yml"
    workflow_path.write_text(workflow_content)
    print(f"  Created: bundle/resources/{agent_name}_workflow.yml")


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print(f"\nScaffolding new agent: {args.name}")
    print(f"Description: {args.description}\n")

    scaffold_agent(
        agent_name=args.name,
        description=args.description,
        agent_type=args.type,
    )

    print(f"\nNext steps:")
    print(f"  1. Implement _invoke() in reference_agent/agents/{args.name}/agent.py")
    print(f"  2. Add tools in reference_agent/agents/{args.name}/tools.py")
    print(f"  3. Register agent in reference_agent/router/router.py")
    print(f"  4. Add eval samples to reference_agent/eval/eval_{args.name}.jsonl")
    print(f"  5. Run: python scripts/deploy.py --target dev")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold a new AgentOps agent")
    parser.add_argument("--name", required=True, help="Agent name (snake_case, e.g. my_agent)")
    parser.add_argument("--description", required=True, help="Agent description")
    parser.add_argument(
        "--type",
        choices=["rag", "summarization", "generic"],
        default="generic",
        help="Agent type template to use",
    )
    args = parser.parse_args()
    sys.exit(main(args))
