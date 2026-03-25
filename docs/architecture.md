---
title: AgentOps Architecture Reference
description: Complete reference for the AgentOps multi-environment CI/CD architecture
category: architecture
tags: [architecture, ci-cd, databricks, mlflow, unity-catalog]
related_docs:
  - docs/best-practices.md
  - docs/deployment.md
  - docs/ci-cd.md
---

# AgentOps Architecture Reference

## Overview

AgentOps uses a three-workspace architecture driven by Git branch promotion. The same codebase runs in dev, staging, and production with environment-specific configurations provided via Databricks Asset Bundle variables.

**Core principle**: Branch = Environment. Promoting code = merging branches. No manual deploy steps.

## Architectural Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Git Provider                                                    │
│  dev ──────────────────► main ─────────────────► release        │
│    CI trigger ▲             Merge ▲               CD Deploy ▲   │
└─────────────────────────────────────────────────────────────────┘
         │                      │                        │
         ▼                      ▼                        ▼
┌────────────────┐  ┌───────────────────┐  ┌─────────────────────┐
│  Development   │  │     Staging       │  │    Production       │
│                │  │                   │  │                     │
│ Data Prep      │  │ Unit Tests (CI)   │  │ App Deployment      │
│ Agent Dev      │  │ Integration (CI)  │  │ Batch Inferencing   │
│ Evaluation     │  │ Validation (CI)   │  │ MLflow Tracking     │
│ App Deploy     │  │ MLflow Tracking   │  │                     │
│ MLflow Track.  │  │                   │  │                     │
└────────────────┘  └───────────────────┘  └─────────────────────┘
         │                      │                        │
         └──────────────────────┴────────────────────────┘
                          Unity Catalog / Lakehouse
                  Dev Catalog (r/w) │ Prod Catalog (read-only from dev)
```

## Development Workspace

### Data Preparation Workflow

Runs on `dev` branch. Prepares all data assets agents need.

**Structured path**: Data Ingestion → Chunking → Vector Search Indexing

**Unstructured path**: ai_parse_document → ai_query_extraction → Data Preparation

Both paths converge on the Dev Catalog Vector Search index.

### Agent Development Workflow

Runs on `dev` branch. Iterative agent build loop.

```
Agent Router Dev ──► Agent 1 Tools ──► Agent 1 Dev ──► Agent 1 Eval
                └──► Agent 2 Tools ──► Agent 2 Dev ──► Agent 2 Eval
```

Evaluation must pass thresholds before committing.

### App Deployment Workflow

Packages agents, registers in Unity Catalog, deploys to Model Serving endpoint.

```
Agent 1 Deploy ──┐
Agent 2 Deploy ──┴──► App Deploy ──► Model Serving Endpoint
```

### SME Human-in-the-Loop

Subject Matter Expert reviews:
- Agent traces in MLflow
- Live agent outputs via Model Serving endpoint
- Logs structured feedback to MLflow (creates auditable record)

## Staging Workspace

Automated quality gate. No human intervention expected.

| Test Type | What It Tests | Reads From |
|---|---|---|
| Unit Tests (CI) | Isolated component logic | Python only |
| Integration Tests (CI) | External system interactions | Dev Catalog |
| Validation Tests (CI) | End-to-end agent quality | Dev Catalog + agents |

All results logged to Staging MLflow. All three tiers must pass to promote.

## Production Workspace

Live environment serving real users.

**App Deployment**: Mirror of dev App Deployment but on `release` branch. Reads from and writes to Prod Catalog.

**Batch Inferencing**: Scheduled Spark jobs calling Model Serving endpoint for large-scale processing.

**MLflow Tracking**: Continuous production trace logging enables drift detection and quality monitoring.

## Unity Catalog

| Catalog | Access from Dev | Access from Prod |
|---|---|---|
| Dev Catalog | Read/Write | None |
| Prod Catalog (dev-facing) | Read-only | N/A |
| Prod Catalog (prod-facing) | None | Read/Write |

The read-only constraint on Prod Catalog from dev is enforced by UC permissions, not by application logic.

## Key Architecture Principles

1. **Branch = Environment** — No manual deploy steps. CI/CD handles it.
2. **MLflow Tracing Everywhere** — Every workspace has full observability.
3. **Evaluation Before Promotion** — Quality gates block bad agents from reaching prod.
4. **Human Review at Dev** — SME feedback before any CI trigger.
5. **Registered Assets Govern Promotion** — UC models with `@champion` alias are what gets served.
6. **Single-Account, Multi-Environment** — Isolation via catalog namespaces, not separate accounts.

See the full component inventory in `agentops_architecture_decomposition.md`.
