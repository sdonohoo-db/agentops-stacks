# AgentOps Stacks — Implementation Plan

**Status:** Active
**Last Updated:** 2026-04-15

Design principles, architecture, and standing requirements are in
[design-and-architecture.md](design-and-architecture.md).

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

## Progress Summary

### Completed

| Step | What | Status |
|------|------|--------|
| Step 2 | Empty DAB scaffold | Done |
| Step 3 | CLI stitching validation | Done |
| Step 4a | `agent_app` component | Done |
| Step 4b | `mcp_server` component | Done |
| — | Chat UI removal | Done (removed, will revisit as component) |
| — | Repo rebase | Done (PR databricks-solutions/agentops-stacks#4) |

### In Progress

| Step | What | Owner | Status |
|------|------|-------|--------|
| Step 0 | Per-component eval + compliance research | Ongoing | Scoped to agent_app, mcp_server done informally; formal research pending |
| Step 1 | Eval gating and HITL design | Alex (colleague) | Eval framework coming from redux lineage |

### Not Started

| Step | What | Blocked by |
|------|------|------------|
| Step 4c | `vector_search` component | — |
| Step 4d | `agent_model_serving` component | — |
| Step 4e | Eval integration into agent components | Step 1 (eval framework) |
| Step 5 | RAG solution template | Steps 4c + 4e |
| Step 6+ | Additional components and templates | Step 5 milestone |

## Structure

The plan has two tracks: a **fast track** to reach a minimal working state for
stakeholder validation, and a **depth track** of research and design that runs
in parallel and feeds into later steps.

The fast track goal: demonstrate two things:
1. **Composability** — building a solution from an empty DAB by adding components
2. **RAG solution pattern** — a complete, deployable RAG with eval gates

```
FAST TRACK (minimal working state)         DEPTH TRACK (runs in parallel)
─────────────────────────────────          ─────────────────────────────────
Step 2: Empty DAB scaffold        ✓  ←→   Step 0: Eval + compliance research
Step 3: CLI stitching validation  ✓  ←→     (scoped to agent + vector_search
Step 4: Base components                ←→      first, broader catalog later)
  ✓ agent_app                          ←→   Step 1: Eval gating + HITL design
  ✓ mcp_server                         ←→     (Alex — eval framework from redux)
  · vector_search
  · agent_model_serving
  · eval integration (after Step 1)
            │
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

The MLflow Prompt Registry analysis (see Design Priority #5 in design-and-architecture.md)
is the model for this research. The answer is rarely "don't use it" — it's usually
"here's how to use it safely, and here's what to turn off in regulated environments."

**Known evaluation mechanisms by component type:**

| Component Type | Eval Mechanism | Customer-Provided Assets | Status |
|---|---|---|---|
| Agent responses (any framework) | `mlflow.evaluate()` with LLM-judged scorers | Ground-truth Q&A dataset | SDK available |
| RAG retrieval quality | Retrieval-specific scorers (relevance, chunk_relevance) | Q&A dataset with expected source docs | SDK available |
| Knowledge Assistant (Agent Bricks) | Guidelines API | Declarative behavior rules | Investigate SDK |
| Genie Spaces | Benchmarks API | Golden question/SQL/answer dataset | Investigate SDK |
| MCP servers | Tool call correctness, schema compliance | Expected tool call/response pairs | Research needed |
| Data prep / ingestion | Data quality checks, schema validation | Expected schema, row count bounds | Standard tooling |
| Guardrails / safety | Safety scorers, adversarial test sets | Red-team prompts, PII test data | SDK available |
| Prompt Registry | N/A (authoring tool, not runtime) | N/A | Beta — not HIPAA-listed, non-PHI only |

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

**Status:** Alex is bringing the eval framework from the redux lineage. The eval
gating logic (EvaluationThresholds, presets, quality gates), online evaluation
(OnlineEvaluator, trace sampling), and HITL feedback loop (trace annotation, negative
trace export) from redux are the starting point. These need to be refactored into
components that fit the manifest-driven architecture.

## Step 2: Empty DAB Scaffold — DONE

The base template generated by `databricks bundle init` produces a clean, empty DAB
with no agent code or agent-specific resources baked in.

**What shipped:**

- `databricks.yml` with three-environment target structure (dev/staging/prod) and
  `bundle: engine: direct`.
- `include` patterns in `databricks.yml` that auto-discover resource files in
  `resources/`, so components are added by dropping files without editing root config.
- An MLflow experiment resource (every project needs at least one).
- CI/CD workflow templates for GitHub Actions, Azure DevOps, and GitLab.
- `pyproject.toml`, `.env.example`, `.gitignore`, `pytest.ini`.
- Setup script with interactive menu for selecting project type.

**Validated:**

- `databricks bundle validate` passes with zero components (empty DAB).
- A component resource file dropped into `resources/` is picked up by `include`
  without editing `databricks.yml`.

## Step 3: Validate Component Stitching via CLI — DONE

The setup script (`scripts/setup.py`) implements CLI-driven component assembly. The
manifest-driven approach works:

**What shipped:**

- Component manifest format (`component.md` with YAML frontmatter) defining copies,
  modifications, dependencies, external sources, and platform resources.
- `install_components()` reads manifests, copies files, applies modifications
  (append_list, add_dependencies, add_entry_points, set_command, merge_env),
  injects hatch entry points, and replaces instance name placeholders.
- Components are self-contained: adding one doesn't require editing another.
- `components/` directory is deleted after installation (one-time setup operation).

**Key findings from implementation:**

1. **YAML merging via `include` works well.** Component resource files go in
   `resources/` and are auto-discovered. No root `databricks.yml` edits needed
   for resource declarations.
2. **`sync.include` growth is manageable.** Each component adds its source
   directories via the `append_list` modification action. No DAB limitations
   encountered.
3. **Ordering is safe for independent components.** agent_app and mcp_server
   install independently without conflicts. Component-to-component dependencies
   (e.g., agent referencing a vector search index) will need cross-reference
   wiring — not yet tested.
4. **Not idempotent.** Components can't be re-added or removed after installation
   since `components/` is deleted. This is acceptable for the current one-time
   setup model. A future `agentops add <component>` CLI could support incremental
   addition, but that's a separate effort.
5. **`sync.exclude` patterns must match files.** DAB warns on patterns that don't
   match anything. Don't add exclude patterns for directories that are cleaned up
   during setup.

## Step 4: Base Components — IN PROGRESS

### agent_app — DONE

MLflow AgentServer-based agent deployed as a Databricks App.

**What shipped:**

- Component manifest with copies, modifications (sync.include, add_dependencies,
  add_entry_points), and platform resources.
- `agent_server/agent.py` with standalone function pattern — `handle_stream()` and
  `handle_invoke()` are plain async functions, registered with `invoke()`/`stream()`
  decorators separately. This makes them directly callable for testing without going
  through the AgentServer middleware.
- `agent_server/start_server.py` — FastAPI dev server with `/test` route that calls
  `handle_invoke()` directly, demonstrating how to add custom routes and test agent
  logic.
- `app.yaml` with `uv run start-server` command.
- DAB app resource definition in `resources/app-resource.yml`.

**Key learnings:**

- MLflow's `@invoke()` and `@stream()` decorators wrap functions and make them not
  directly callable through the decorator. The standalone function pattern
  (define function, then `invoke()(handle_invoke)`) is required for testability.
- `create_text_delta(delta, item_id)` requires an `item_id` parameter — the API
  signature is not just `create_text_delta(delta)`.
- The platform injects `/health` automatically on deployed Databricks Apps. The
  `/test` route is app-defined and serves as a pedagogical example for users.

**Not yet included:** Evaluation. The agent_app ships without eval gates pending
the eval framework from Step 1.

### mcp_server — DONE

FastAPI + FastMCP combined server deployed as a Databricks App.

**What shipped:**

- Component manifest with copies, modifications (sync.include, add_dependencies,
  add_entry_points), and platform resources.
- `server/app.py` — FastAPI app that mounts the FastMCP SSE transport and exposes
  `/test` route calling a registered tool directly.
- `server/tools.py` — standalone tool functions registered programmatically via
  `mcp_server.tool(func)`. Demonstrates how to add tools to the MCP server.
- `server/utils.py` — Databricks workspace client with OBO token forwarding.
- `server/main.py` — Uvicorn entry point.
- `app.yaml` with `uv run custom-mcp-server` command.
- DAB app resource definition in `resources/app-resource.yml`.

**Key learnings:**

- FastMCP supports both `@mcp_server.tool` decorator and `mcp_server.tool(func)`
  programmatic registration. The programmatic approach keeps tool logic in a
  separate file, mirroring the standalone function pattern from agent_app.
- MCP tools that interact with Databricks APIs need OBO token forwarding from the
  app platform headers.

**Not yet included:** Evaluation. MCP server eval (tool call correctness, schema
compliance) needs research — no established eval mechanism exists yet.

### vector_search — NOT STARTED

Vector Search endpoint and index with Delta Sync. Required for the RAG demo.

This is the next component to build. It will validate component-to-component
cross-references (agent referencing a vector search index) — the key stitching
question that hasn't been tested yet.

Vector Search index is not a first-class DAB resource type, so it will need
notebook-based creation with documentation about why and a note to migrate when
DAB support lands.

### agent_model_serving — NOT STARTED

Model Serving Endpoint-hosted agent with AI Gateway. Second agent hosting pattern.

Agent hosting is a component choice, not a global setting:

| Pattern | Component | When to use | Status |
|---|---|---|---|
| Databricks App | `agent_app` | Chat UI, interactive use, rapid iteration | Done |
| Model Serving Endpoint | `agent_model_serving` | API-first, high throughput, AI Gateway guardrails | Not started |
| External (non-Databricks) | `agent_external` | Agent hosted elsewhere, governed via UC connection + registry | Future (pending first-class UC support) |

All three produce agents that emit standard MLflow/OTel traces, so eval and
monitoring components work the same regardless of hosting pattern.

## Reviewable Milestone: Minimal Working Demo

After Step 4 is complete (vector_search + eval integration), we can demo both
composability and a complete solution pattern using the same components:

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
- Chat UI component (revisit as a proper component with manifest-driven installation)
- Lakebase resource component
- Document Intelligence solution template
- Process Automation solution template
- AI coding assistant skills / MCP server (from redux)
- Online monitoring / production eval component (from redux)
- Cost tracking component (MLflow token logging, from redux)

## What Was Kept from Each Lineage

### From agentops-stacks (this repo)
- DAB template structure and project generation via `databricks bundle init`
- 5-question init questionnaire (cookiecutter)
- CI/CD workflow templates (GitHub Actions, Azure DevOps, GitLab)
- Direct engine deployment pattern
- Setup script architecture (template menu, component installation)
- Three-environment target structure (dev/staging/prod)

### From agentops-stacks-redux (merged in)
- Component manifest concept (extended into YAML frontmatter format)
- MCP server component pattern
- Reference agent implementation patterns
- Workspace client with OBO token forwarding

### Built New
- Component manifest format (`component.md` with YAML frontmatter) and
  `install_components()` to parse and apply it
- Standalone function pattern for agent and MCP tool testability
- `/test` routes as pedagogical examples in both component types
- `sync.include` and dependency injection via manifest modification actions
- Automatic `components/` cleanup after installation

### Still to Integrate from Redux
- Evaluation framework (EvaluationThresholds, presets, quality gate logic)
- Online evaluation / production monitoring (OnlineEvaluator, trace sampling)
- Human-in-the-loop feedback loop (trace annotation, negative trace export)
- Cost tracking (MLflow token logging)

## Open Questions

1. **Component-to-component cross-references.** How does an agent component reference
   a vector search index added by another component? The manifest `modifies` system
   handles simple additions (sync.include, dependencies), but wiring runtime references
   between components hasn't been tested. The vector_search component will be the
   first test of this.

2. **Eval component packaging.** Should evaluation be a standalone component that
   attaches to any agent, or embedded in each agent component's manifest? The design
   says "every component that can be evaluated ships with evaluation built in" — but
   the eval framework itself needs to be shared. Likely answer: a shared eval library
   component that agent components depend on, with per-component eval configuration
   in each agent's manifest.

3. **Chat UI as component.** The chat UI (from `databricks/app-templates`
   `e2e-chatbot-app-next`) was removed because it introduced a nested bundle
   (`databricks.yml` inside the cloned directory) and added complexity without
   sufficient value at this stage. Revisiting it as a proper component with
   `remove_after_fetch` in the manifest's `external_sources` is the right path,
   but not until the core component set is stable.

4. **Incremental component addition.** The current model is one-time setup: choose
   components, install, done. A future `agentops add <component>` flow for adding
   components to an existing project would improve the developer experience, but
   requires solving idempotency and dependency resolution. Not blocking for the
   milestone.

5. **Quick-start examples (Path A).** The setup script's `external_sources` mechanism
   already supports importing from `databricks/app-templates`. The menu could offer
   specific app-templates entries as quick-start options. This is a UX enhancement,
   not a structural change.
