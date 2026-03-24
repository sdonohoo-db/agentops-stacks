---
title: AgentOps Reference Agent
description: Complete working multi-agent RAG application demonstrating the full AgentOps framework
category: reference
tags: [reference, rag, multi-agent, example]
---

# AgentOps Reference Agent

A complete, runnable multi-agent application demonstrating every layer of the AgentOps framework. Use this as the starting point for your own agent projects.

## What This Is

A two-agent RAG application with a shared router:

| Agent | Name | What It Does |
|---|---|---|
| Agent 1 | `rag_agent` | Retrieval-augmented Q&A — answers questions from the knowledge base |
| Agent 2 | `summarization_agent` | Summarizes documents with structured output |
| Router | `agent_router` | Classifies intent and dispatches to the right agent |

## Quick Start

```bash
# Run a local smoke test (no Databricks needed)
python reference_agent/app.py test

# Deploy to dev workspace
python reference_agent/app.py deploy
```

## Files

```
reference_agent/
├── app.py                      # Entry point (mlflow.pyfunc model)
├── config.yaml                 # Agent configuration
├── agents/
│   ├── agent1/
│   │   ├── agent.py            # RAGAgent implementation
│   │   └── tools.py            # UC tools (search_knowledge_base, etc.)
│   └── agent2/
│       ├── agent.py            # SummarizationAgent implementation
│       └── tools.py            # UC tools (get_document_for_summary, etc.)
├── router/
│   └── router.py               # AgentRouter wiring (build_router())
├── eval/
│   ├── eval_dataset.jsonl      # 20 eval samples for both agents
│   └── run_eval.py             # Evaluation runner
└── data/
    └── sample_documents/       # Sample text files for the knowledge base
```

## Running Evaluation

```bash
# Evaluate all agents
python reference_agent/eval/run_eval.py

# Quick 5-sample check
python reference_agent/eval/run_eval.py --sample 5

# Specific agent
python reference_agent/eval/run_eval.py --agent rag_agent
```

## Customizing

1. Replace `reference_agent/data/sample_documents/` with your own documents
2. Update `eval/eval_dataset.jsonl` with domain-specific questions
3. Adjust `config.yaml` for your LLM endpoint and chunk settings
4. Add domain-specific tools in `agents/agent1/tools.py`

For a new agent, use `python scripts/scaffold.py --name my_agent --type rag`.
