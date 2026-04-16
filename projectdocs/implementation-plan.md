# AgentOps Stacks — Implementation Plan

**Status:** Replanning
**Last Updated:** 2026-04-14

Design principles, architecture, and standing requirements are in [CLAUDE.md](CLAUDE.md).

## Tooling Architecture

The implementation builds toward this modular architecture. The diagram is the
reference for how the three content paths, three user interfaces, and the DAB output
fit together.

```
 USER INTERFACES           THREE PATHS TO POPULATE A DAB             DAB                  CI/CD
 (how you build)           (pick one to start, mix in components)    (project structure)  (how it ships)

                           ┌─────────────────────────────────────┐
                     ┌────▶│  A. Quick-Start Examples             │
                     │     │     Imported from databricks/        │
                     │     │     app-templates repo               │
                     │     │                                      │
                     │     │     langgraph, openai-sdk,           │
 ┌─────────────────┐ │     │     mcp-server, multi-agent, ...    │
 │  CLI Tools      │ │     │     Fastest path. Minimal agent     │──┐
 │  (bundle init,  │ │     │     app, no ops scaffolding.        │  │
 │   setup script) │─┤     └─────────────────────────────────────┘  │
 │                 │ │                                               │
 ├─────────────────┤ │     ┌─────────────────────────────────────┐  │
 │  Drag-and-Drop  │ │     │  B. Solution Templates              │  │   ┌──────────────┐   ┌──────────────┐
 │  App Builder    │─┼────▶│     Pre-assembled from components   │  │   │              │   │              │
 │                 │ │     │     for common production patterns  │  │   │  Databricks  │   │  GitHub      │
 ├─────────────────┤ │     │                                      │  │   │  Asset       │   │  Actions     │
 │  Coding Agent   │ │     │     RAG                             │  ├──▶│  Bundle      │──▶│              │
 │  Skills         │─┤     │     Document Intelligence           │  │   │              │   │  Azure       │
 │  (Claude Code,  │ │     │     Process Automation              │  │   │  databricks  │   │  DevOps      │
 │   Cursor, etc.) │ │     │     Multi-agent                     │──┘   │  .yml        │   │              │
 └─────────────────┘ │     │     Best-practice architecture,     │      │  resources/  │   │  GitLab      │
                     │     │     ready to init and deploy.       │      │  targets/    │   │              │
                     │     └─────────────────────────────────────┘      │              │   └──────┬───────┘
                     │                                                  └──────┬───────┘          │
                     │     ┌─────────────────────────────────────┐            │                  │
                     │     │  C. Component Assembly               │            │                  ▼
                     └────▶│     Discrete modules added to a      │            │        ┌──────────────────┐
                           │     blank DAB one at a time          │            │        │  Dev / Staging /  │
                           │                                      │──(blank)──▶│        │  Prod Workspaces  │
                           │     Eval gates                      │            │        │                  │
                           │     Monitoring / observability      │            └───────▶│  Apps, Jobs,     │
                           │     Data prep pipelines             │                    │  Endpoints,      │
                           │     MCP servers                     │                    │  Experiments     │
                           │     Lakebase / VS / UC resources    │                    └──────────────────┘
                           │     CI/CD workflow configs           │
                           │     Pick what you need, skip        │
                           │     what you don't.                 │
                           └─────────────────────────────────────┘
```

The fast track validates paths A and C with two components (agent_app + vector_search).
Path B (solution templates) follows at Step 5 by freezing the assembled result.

## Structure

The plan is structured in two tracks: a **fast track** to reach a minimal working state
we can validate with stakeholders, and a **depth track** of research and design that
runs in parallel and feeds into later steps.

The fast track goal: demonstrate two things as quickly as possible:
1. **RAG solution pattern** — a complete, deployable RAG solution with eval
2. **Composability** — building that same RAG from an empty DAB by adding components
   (agent_app + vector_search)

Both demos use the same two components (agent, vector store), which means we get
two proof points from a minimal build. The RAG template is a pre-assembled version
of what the component assembly path produces.

```
FAST TRACK (minimal working state)         DEPTH TRACK (runs in parallel)
─────────────────────────────────          ─────────────────────────────────
Step 2: Empty DAB scaffold            ←→   Step 0: Eval + compliance research
Step 3: CLI stitching validation      ←→     (scoped to agent + vector_search
Step 4: agent_app + vector_search     ←→      first, broader catalog later)
         components with eval          ←→   Step 1: HITL and gating design
            │                                Step 1: Eval Ops lifecycle design
            ▼
   *** Reviewable milestone ***
   Demo A: composability (primary)
     empty DAB → add agent_app
     → add vector_search → deploy
     → eval gate → feedback loop
   Demo B: RAG template (from A)
     freeze assembled result into
     a pre-built init template
            │
            ▼
Step 5: Package Demo A → RAG template
Step 6+: Expand component catalog
```

## Step 0: Per-Component Research (Evaluation + Compliance)

For every potential component of an AI solution on Databricks, research the documentation
to fully understand two things: (1) what evaluation and improvement mean for that
component, and (2) what data flows through it and what compliance implications that
creates. These are not separate activities — they inform the same design decisions.

**Evaluation questions (per component):**

- What does "evaluation" mean for this component? What is being measured?
- Is there a specific Databricks mechanism/API for evaluating it? If so, how should it
  be implemented in or alongside the component?
- What assets must the customer bring to the evaluation mechanism? (datasets, guidelines,
  benchmarks, ground truth, etc.)
- How do evaluation results feed back into the development cycle? (closed-loop)

**Compliance questions (per component):**

- What data flows through this component? (prompts, responses, embeddings, traces,
  customer data, PII, PHI, etc.)
- Where is that data stored or logged? (MLflow experiment, UC table, workspace storage,
  external service)
- Is the component GA or preview/beta? If preview, is it listed under "Supported
  preview features" in the compliance security profile docs?
- What configuration is required to make it compliant in regulated environments?
  (CSP settings, workspace admin toggles, data masking, access controls)
- Can the component be disabled or scoped to non-sensitive data without breaking the
  rest of the solution?

The MLflow Prompt Registry analysis (see Design Priority #5 in CLAUDE.md) is the model
for this research. The answer is rarely "don't use it" — it's usually "here's how to
use it safely, and here's what to turn off in regulated environments."

**Known evaluation mechanisms by component type:**

| Component Type | Eval Mechanism | Customer-Provided Assets | Status |
|---|---|---|---|
| Agent responses (any framework) | `mlflow.evaluate()` with LLM-judged scorers | Ground-truth Q&A dataset | SDK available |
| RAG retrieval quality | Retrieval-specific scorers (relevance, chunk_relevance) | Q&A dataset with expected source docs | SDK available |
| Knowledge Assistant (Agent Bricks) | Guidelines API | Declarative behavior rules | Investigate SDK |
| Genie Spaces | Benchmarks API | Golden question/SQL/answer dataset | Investigate SDK |
| MCP servers | TBD — tool call correctness, schema compliance? | TBD | Research needed |
| Data prep / ingestion | Data quality checks, schema validation | Expected schema, row count bounds | Standard tooling |
| Guardrails / safety | Safety scorers, adversarial test sets | Red-team prompts, PII test data | SDK available |
| Prompt Registry | N/A (authoring tool, not runtime) | N/A | Beta — not HIPAA-listed, non-PHI only |

This research drives every other step. Do not design a component's eval or recommend
its inclusion without understanding both the evaluation mechanism and the data flow.

**For the fast track:** scope this research to `agent_app` and `vector_search` first —
these are the two components needed for the reviewable milestone (RAG demo +
composability demo). Broader catalog research continues in the depth track.

## Step 1: Evaluation Gating and Human-in-the-Loop Design

Two distinct evaluation mechanisms need design work:

**Automated eval gates (CI/CD):**
The CI/CD pipeline needs gates that execute judges against eval datasets and block
promotion on failure. The existing CI/CD workflow templates do not include this yet.
Design questions:
- Where in the pipeline do eval gates run? (after deploy to staging, before promote
  to prod?)
- What does a gate step look like? (DAB job task? CI/CD step that calls
  `mlflow.evaluate()`?)
- What happens on failure? (block promotion, alert, require manual override?)

**Human-in-the-loop evaluation (async feedback):**
HITL does not gate the operational flow. Instead, the flow raises concerns (flagged
traces, low-confidence responses, monitoring alerts) that require human attention.
Humans review traces, annotate issues, and the outcome produces new assets to include
in the bundle — an optimized prompt, a new custom judge, new entries in the eval
dataset. This is the "two-motion cycle" from the Eval Ops concept: humans improve
the benchmark, developers improve the agent.

Design questions for HITL:
- Where do humans review? (MLflow experiment UI? Databricks App? External tool?)
- How does a flagged trace become an eval dataset entry or a prompt revision?
- What artifacts does HITL produce, and how do they flow back into the DAB?

**CI/CD template assessment:**
Review the current GitHub Actions / Azure DevOps / GitLab templates from
agentops-stacks. Do they support adding eval gate steps, or do they need structural
rework?

## Step 2: Empty DAB Scaffold

**This is the first change to the agentops-stacks repo.** The base template generated
by `databricks bundle init` should be truly empty — no agent code, no agent-specific
resources. Currently, the template bakes in `agent_server/`, `agent_deployment/`,
`agent_development/`, and `app.yaml` regardless of what the user wants. These should
be moved out of the base template and into setup — added only when the user picks an
agent template. A user who wants only an MCP server or a vector index should not have
to delete agent scaffolding.

Also: the template still includes leftover MLOps Stacks documentation images
(`docs/images/mlops-stack-deploy.png`, `docs/images/mlops-stack-summary.png`) that
need to be removed.

**Scaffold includes:**

- `databricks.yml` with three-environment target structure (dev/staging/prod). Users
  without a staging or QA workspace can remove it manually after init.
- `include` patterns in `databricks.yml` that auto-discover resource files in
  `resources/`, so components can be added by dropping files without editing root config.
- An MLflow experiment resource (every project needs at least one; users can add more).
- `resources/` directory for modular component resource definitions.
- CI/CD workflow stubs (user picks provider during init).
- `pyproject.toml`, `.env.example`, `.gitignore`.

**Validation criteria:**

- `databricks bundle validate` passes with zero components.
- `databricks bundle deploy --target dev` with the direct engine creates the expected
  workspace state (experiment, empty resource directory).
- A component resource file dropped into `resources/` is picked up by `include`
  without editing `databricks.yml`.

**Open question: component-to-component integration.** Adding standalone components
via `include` is straightforward — drop a resource file, it gets discovered. The harder
problem is when components need to reference each other after being added (e.g., an
agent component referencing a vector search index, an eval job referencing an agent
endpoint). How those cross-references are wired is an open design question for Step 3.

The existing setup script (which populates the bundle after init) stays as-is for now
and will be updated as components are integrated.

This is the foundation everything else gets added to. If the empty scaffold doesn't
work, nothing built on top of it will.

## Step 3: Validate Component Stitching via CLI

Modularity and composability assume we have a reliable way to stitch components into
an existing DAB correctly. The three interfaces have different levels of confidence:

| Interface | Confidence | Why |
|---|---|---|
| Coding assistant + skills | High | Reads the manifest, understands the project, can make judgment calls about file placement and config merging |
| Graphical UI / drag-and-drop | High | Controlled environment, can enforce valid combinations and generate correct configs programmatically |
| CLI | Uncertain | Must handle file copying, YAML merging, variable injection, and `sync.include` updates without an intelligent agent in the loop |

The CLI is the riskiest interface and must be validated early — before investing in
building many components that assume CLI-driven assembly works.

Test with the empty scaffold from Step 2 and the existing prototype components
(agent_app_base, vector_index) in `components/`:

1. **What does "add a component" look like from the CLI?** Is it a single command
   (`agentops add vector_search`)? A script that reads the manifest and copies
   artifacts? A guided questionnaire? What is the minimal viable UX?
2. **YAML merging**: Adding a component means merging its `databricks.yml` snippet
   into the project. DAB supports `include` directives — can component resource files
   simply be dropped into `resources/` and auto-included? Or do they require edits to
   the root `databricks.yml`? Test both approaches.
3. **Variable conflicts**: Two components may introduce variables with the same name
   or conflicting defaults. How does the CLI detect and resolve this?
4. **`sync.include` growth**: Each component may add source directories that need
   syncing. Does this scale cleanly, or does it hit DAB limitations?
5. **Ordering and idempotency**: Can components be added in any order? Can a component
   be added twice without breaking the project? Can a component be removed?
6. **Validation after stitching**: After adding a component via CLI, does
   `databricks bundle validate` pass? Does `deploy` succeed? Test the full round trip.

If CLI-driven stitching proves too brittle or limited, that's a finding — it means
the component model may need to be CLI-optional (coding assistant and UI only) with
the CLI limited to whole-template operations. Better to learn this now than after
building 15 components.

## Step 4: Base Components

Build, test, and document the first set of components on the empty scaffold.
Use these to validate the stitching approach identified in Step 3:

| Component | Description | Eval Mechanism (from Step 0) |
|---|---|---|
| `agent_app` | Databricks App-hosted agent with MLflow experiment | `mlflow.evaluate()` + LLM scorers |
| `agent_model_serving` | Model Serving Endpoint-hosted agent with AI Gateway | `mlflow.evaluate()` + LLM scorers |
| `vector_search` | Vector Search endpoint and index with Delta Sync | Retrieval scorers, index sync validation |

Agent hosting is a component choice, not a global setting. These are the first two
of three agent hosting patterns:

| Pattern | Component | When to use | Status |
|---|---|---|---|
| Databricks App | `agent_app` | Chat UI, interactive use, rapid iteration | Fast track |
| Model Serving Endpoint | `agent_model_serving` | API-first, high throughput, AI Gateway guardrails | Fast track |
| External (non-Databricks) | `agent_external` | Agent hosted elsewhere, governed via UC connection + registry | Future (pending first-class UC support) |

All three produce agents that emit standard MLflow/OTel traces, so eval and
monitoring components work the same regardless of hosting pattern.

For each component:
1. Build the DAB artifacts and component manifest
2. Add to the empty scaffold, validate, deploy
3. Implement the eval mechanism identified in Step 0
4. Verify that adding one component doesn't break another already present
5. Verify the closed-loop: eval results → actionable feedback in dev

## Reviewable Milestone: Minimal Working Demo

After Step 4, we can demo both composability and a complete solution pattern using
the same two components:

**Demo A — Composability (primary):**
Empty DAB scaffold → add `agent_app` component → add `vector_search` component
→ deploy with direct engine → eval gate runs → passes or fails → feedback loop
shows how to improve in dev. Demonstrates the component model end-to-end.

**Demo B — RAG Solution Template (follows from A):**
If composability works, the RAG template is a natural outcome: freeze the assembled
result from Demo A into a pre-built template that users can init directly. Demo B
is not a separate build — it's Demo A packaged as a starting point for users who
just want RAG without assembling it themselves.

**Use this milestone to validate:**
- Is the component model intuitive? Can someone see how it scales to their use case?
- Is the eval integration convincing? Does it feel built-in, not bolted on?
- Does CLI stitching work, or do people want a different interface?
- Is the approach sound before investing in the full component catalog?

Delivery targets (ML-SME presentation, customer workshops) are in `project-notes.md`.

## Step 5: Package RAG Solution Template

Freeze the successfully assembled Demo A (agent_app + vector_search + eval) into a
pre-built DAB template that users can init directly. This is not a separate build —
it's the composability result packaged as a starting point.

The template should be a snapshot of what the component assembly path produces, so
that a user who inits the RAG template gets the exact same project structure as
someone who assembled it from components. This keeps the two paths consistent and
means the template stays up to date as the components evolve.

RAG template includes:
- Agent app with MLflow experiment
- Vector Search index with Delta Sync
- Evaluation with retrieval-specific scorers + response quality
- CI/CD with eval-gated promotion
- Production monitoring with feedback loop back to eval datasets

## Step 6+: Additional Components and Templates

Expand based on priorities from Tim sync. Candidates:
- Genie agent component + Benchmarks evaluation
- Knowledge Assistant component + Guidelines evaluation
- MCP server component
- Lakebase resource component
- Document Intelligence solution template
- Process Automation solution template
- AI coding assistant skills / MCP server (from redux)
- Online monitoring / production eval component (from redux)

## What to Keep from Each

### From agentops-stacks
- DAB template structure and cookiecutter-based project generation
- 5-question init questionnaire
- CI/CD workflow templates (GitHub Actions, Azure DevOps, GitLab)
- Direct engine deployment pattern
- Agent-agnostic app resource definition
- Setup script architecture (template menu, sparse checkout from app-templates)

### From agentops-stacks-redux
- Evaluation framework (EvaluationThresholds, presets, quality gate logic)
- Online evaluation / production monitoring (OnlineEvaluator, trace sampling)
- Human-in-the-loop feedback loop (trace annotation, negative trace export)
- MCP server and AI coding platform integration
- Scaffold CLI for adding agents
- Reference agent implementation patterns (AgentBase, router, tool registry)
- Comprehensive documentation and troubleshooting structure
- Cost tracking

### Build New
- Component manifest format and tooling to parse it
- Empty DAB scaffold validated with direct engine
- Per-component evaluation wiring (connecting eval mechanisms to components)
- Closed-loop feedback infrastructure (production → dev pipeline)
- Model serving endpoint component (redux has it as deployment, needs componentization)
