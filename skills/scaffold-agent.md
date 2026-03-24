---
name: scaffold-agent
description: Scaffold a new agent project from AgentOps templates
trigger: /scaffold-agent
category: development
tags: [agentops, agent, scaffold, template]
---

Create a new agent using the AgentOps framework templates, with all required boilerplate.

## When to use
Use this skill when the user wants to:
- Add a new specialized agent to their multi-agent application
- Start a new agent project from scratch using AgentOps patterns
- Create an agent with tools, eval dataset, and DAB workflow pre-wired

## What you should do

1. **Gather requirements** — ask if not provided:
   - Agent name (snake_case, e.g., `policy_lookup_agent`)
   - Agent description (what does it do?)
   - Agent type: `rag` (retrieval), `summarization`, or `generic`

2. **Scaffold the agent**:
   ```bash
   python scripts/scaffold.py \
     --name <agent_name> \
     --description "<description>" \
     --type <rag|summarization|generic>
   ```

3. **Explain what was created**:
   - `reference_agent/agents/<name>/agent.py` — Agent class to implement
   - `reference_agent/agents/<name>/tools.py` — UC tool registration
   - `reference_agent/eval/eval_<name>.jsonl` — Starter eval dataset
   - `bundle/resources/<name>_workflow.yml` — DAB workflow

4. **Guide next steps**:
   - Implement `_invoke()` in `agent.py`
   - Add tools in `tools.py`
   - Register in `reference_agent/router/router.py`
   - Add real eval samples to the JSONL file
   - Deploy: `python scripts/deploy.py --target dev`

## Key files
- `scripts/scaffold.py` — Scaffolding script
- `framework/agent_development/agent_base.py` — Base class to extend
- `framework/agent_development/tool_registry.py` — Tool registration API
- `reference_agent/agents/agent1/agent.py` — Reference implementation (RAG)
- `reference_agent/agents/agent2/agent.py` — Reference implementation (Summarization)

## Tips
- Use the existing RAG agent (`agent1/agent.py`) as a reference for retrieval-based agents
- The router uses keyword matching first — add relevant keywords when registering
- Always add at least 10 eval samples before deploying to staging
