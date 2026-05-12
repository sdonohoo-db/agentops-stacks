# AgentOps Stacks — Design Principles & Architecture

**Last Updated:** 2026-05-12

agentops-stacks scaffolds production-ready AI projects on Databricks and guides
them through orchestration, governance, and lifecycle. The project ships two
channels — a DAB template and a portable coding-assistant plugin — that share a
common scaffold contract. Agent code, data pipelines, and platform resources
are created by coding assistants (Claude Code, Cursor, Genie Code) or hand-
written; agentops-stacks owns the operational envelope around them.

Implementation steps, milestones, and current status are in
[implementation-plan.md](implementation-plan.md). The repo's
[AGENTS.md](../AGENTS.md) is the operational standing-requirements doc for
contributors and AI coding assistants. This document is the strategic reference
the team validates against — the "why" behind the requirements.

## Primary Sources

- **Big Book of Agent Ops** (Databricks-internal, Google Doc) — the
  authoritative source for production AI deployment patterns and reference
  architectures on Databricks. The Big Book is currently in draft; once
  finalized it is authoritative, and the agentops-stacks scaffold must not
  deviate from its best practices and reference architectures. Until then,
  this document tracks the draft and the scaffold reflects the best current
  reading. Where this document or the scaffold diverges from the Big Book,
  the divergence is documented as a deliberate delta until the Big Book
  absorbs it or the scaffold realigns. The scaffold may go beyond the Big
  Book where Design Priorities require it, but never against it.
- **AgentOps Field Guide: Evaluation (Veena Ramesh)** — three-tier testing
  framework, golden-dataset lifecycle, judge tier distinctions. Treated as
  authoritative for evaluation-pattern specifics.
- **Databricks AI Security Framework (DASF) 3.0** — baseline security
  practices; the floor, not the ceiling.

## Design Priorities (in order)

1. **Scaffold first, then guide. Don't ship components.**

   The project generates the production envelope — DAB layout, dev/staging/prod
   targets, UC conventions, CI/CD wiring, scaffold contract — and guides the
   solution through orchestration, governance, and lifecycle as it develops.
   Agent code and Databricks resources themselves are not in scope. Those come
   from coding assistants and ai-dev-kit; agentops-stacks composes with them.

   Why this division: coding assistants are already the primary developer
   interface for AI solutions on Databricks, and ai-dev-kit already provides
   the Databricks-specific component skills. Re-implementing component creation
   inside agentops-stacks would compete with those tools instead of complementing
   them. By owning only the envelope, agentops-stacks stays valuable regardless
   of which assistant — or none — the developer uses.

   The architectural consequence: every workflow must be completable through
   the CLI, by editing DAB files directly. Plugins and assistants are
   accelerators; the scaffold and CI/CD wiring stand on their own.

2. **Opinionated evaluation gates.** When evaluation patterns are applied to a
   scaffold, they ship eval-on by default. Agent patterns include quality
   gates. Data patterns include validation checks. Where evaluation isn't yet
   possible (e.g., pending SDK support for Genie Benchmarks or KA Guidelines),
   include a stub that documents what will be evaluated and exits cleanly
   without blocking.

3. **Closed-loop operations, not demos.** Every operational pattern (evaluation,
   monitoring, feedback, optimization) must close the loop back to development
   action. Production evaluation results feed back into dev as new eval dataset
   entries or regression test cases. User/SME feedback on production traces
   becomes annotation candidates. Monitoring alerts map to runbooks or
   automated remediation. The pattern must show not just how to observe a
   deployed agent but how the observation drives the next improvement cycle
   through the dev → staging → prod pipeline. A pattern that only demonstrates
   a capability without connecting it to the feedback loop is incomplete.

4. **Challenge assumptions at every step.** After completing a design decision,
   research task, or implementation step, pose follow-up questions that
   challenge the result or clarify what should come next. Don't just deliver
   an answer — surface what's still uncertain, what could break the assumption,
   or what the next decision depends on. This applies to AI-assisted work
   (Claude should ask, not just execute) and to team collaboration (every
   review should end with "what are we missing?").

5. **Security is not a separate concern — it's built into every pattern.**
   Don't treat security as a standalone checklist applied at the end. Every
   pattern must consider data exposure, credential handling, and compliance
   from the start. For each pattern, document: what data flows through it,
   where that data is stored or logged, and what compliance implications that
   creates.

   **Worked example — MLflow Prompt Registry and HIPAA:** MLflow 3 core
   (tracing, evaluation, models) is HIPAA-supported, but Prompt Registry is
   Beta and not listed under "Supported preview features" — so it's non-PHI
   only. Resolution: disable it in HIPAA workspaces or scope to non-PHI
   templates. This is the level of diligence required for every pattern: what
   is GA vs preview, what data touches it, where does that data land? Each
   pattern's docs cover this.

   Reference DASF 3.0 for baseline practices. But DASF is the floor, not the
   ceiling — regulated industries (healthcare, financial services) have
   additional constraints that the pattern documentation should flag even if
   the pattern can't solve them directly.

   **Our role is guidance, not enforcement.** We can't prevent a customer from
   making inadvisable choices. What we can control:
   - **No lazy defaults.** If there's a more secure way to deploy a resource,
     that's the way the scaffold deploys it. Don't take shortcuts that a
     customer then has to undo — use UC-governed resources, scoped credentials,
     least-privilege permissions, and workspace-boundary data flows by default.
   - **Practical security documentation per pattern.** Each pattern ships with
     documentation on how to secure it in practice — not abstract DASF control
     mappings, but concrete guidance: what to configure, what to restrict,
     what to watch for in production. Written for the person doing the
     deployment, not the person writing the compliance report.

   **Long-term goal: DASF 3.0 posture visibility.** Any solution built with an
   agentops-stacks scaffold should be assessable against DASF 3.0 control
   points. Each pattern's documentation covers which DASF practices it
   implements by default, which require customer configuration, and which are
   outside the pattern's scope. A customer (or their security team) should be
   able to read the pattern docs for their assembled solution and understand
   their security posture without reverse-engineering the deployment.

6. **Integrate with coding assistants, don't replace them.**

   The project integrates with Claude Code, Cursor, Genie Code, and
   [ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit). Coding
   assistants and ai-dev-kit provide the component-creation surface — agents,
   MCP servers, vector indexes, jobs, dashboards, serving endpoints, apps, UC
   resources. agentops-stacks provides the orchestration, governance, and
   lifecycle surface above them.

   Principles:
   - **Self-sufficient without any specific assistant.** Every workflow (init,
     configure, validate, deploy, evaluate, promote) must be completable
     through the CLI or by editing DAB files directly. Documentation describes
     the workflow in terms of what the user does, not which assistant skill to
     invoke. If an assistant makes a step easier, note that — but the step
     must work without it.
   - **Don't rebuild what assistants and ai-dev-kit already do.** If
     ai-dev-kit can create a vector search index or deploy an app, the
     scaffold defines the resource declaratively in the DAB and lets the
     assistant or ai-dev-kit help the user configure it. Competing mechanisms
     for the same action create confusion.
   - **agentops-stacks focuses on what assistants don't cover:** the project
     as a scaffold (DAB generation), the lifecycle (CI/CD, eval gates,
     promotion), the operational loop (monitoring, HITL feedback, closed-loop
     improvement), and the compliance posture (per-pattern security
     documentation, DASF mapping, data flow analysis).
   - **The plugin is one delivery of these skills, not the only one.** The
     agentops-stacks plugin packages the same guidance for use inside an
     assistant. Plugin behavior must remain consistent with the CLI workflow.

## Architecture

Two levels: **target solution architecture** (the multi-environment agent
lifecycle a deployed scaffold implements) and **tooling architecture** (how
agentops-stacks builds and operates on the scaffold).

### Target Solution Architecture

Reference architectures from the Big Book of Agent Ops define the production
patterns scaffolds must conform to. The scaffold must not deviate from the
Big Book's best practices, though it may go beyond them where Design
Priorities require. Where the implementation diverges, the divergence is
documented as a deliberate delta (see
[Deliberate deltas above the Big Book baseline](#deliberate-deltas-above-the-big-book-baseline))
and is treated as temporary — either the Big Book absorbs the delta or the
scaffold realigns.

Four views form a 2x2 matrix — same core architecture, scaled along two axes:

```
                        Single-Agent              Multi-Agent
                   ┌───────────────────────┬───────────────────────┐
  Single-Account   │  Simplest case.       │  Multiple agents in   │
                   │  One agent, three     │  one account. Shared  │
                   │  environments, one    │  catalogs, routing,   │
                   │  UC account.          │  per-agent eval.      │
                   ├───────────────────────┼───────────────────────┤
  Multi-Account    │  Separate accounts    │  Full enterprise      │
                   │  for dev/staging/     │  pattern. Account     │
                   │  prod. Data Sharing   │  isolation + Data     │
                   │  bridges catalogs.    │  Sharing + multi-     │
                   │                       │  agent orchestration. │
                   └───────────────────────┴───────────────────────┘
```

All four share this core lifecycle:

```
  Git Provider
  (feature branch)──────────(main branch)────────────(release branch)──────────────
        │                        │                          │
        ▼                        ▼                          ▼
  ┌─────────────────┐    ┌───────────────────┐    ┌──────────────────────┐
  │  DEVELOPMENT    │    │  STAGING /        │    │  PRODUCTION          │
  │                 │    │  VALIDATION       │    │                      │
  │  Data Prep      │    │  Unit Tests       │    │  Continuous Deploy   │
  │  Agent Dev      │    │  Integration      │    │  App / Endpoint      │
  │  Evaluation     │    │  Validation       │    │  Batch Inference     │
  │  App Deploy     │    │  Pre-prod Eval    │    │  Monitoring          │
  │  (dev target)   │    │  Gates            │    │  Online Eval         │
  └────────┬────────┘    └────────┬──────────┘    └──────────┬───────────┘
           │                      │                          │
      Dev Catalog            Test Catalog              Prod Catalog
           └──────────────────────┴──────────────────────────┘
                            Unity Catalog
```

Multi-account variants add **Data Sharing** between accounts so catalogs in
isolated accounts can exchange data across the dev → staging → prod boundary.

Multi-agent variants add per-agent workflow blocks, routing/orchestration,
and per-agent evaluation within each environment.

### Tooling Architecture

Two channels, both producing or operating on the same scaffold:

```
                         ┌─────────────────────────────────┐
   databricks bundle  ─▶ │  DAB template (canonical)       │ ─┐
   init                  │  Pure-CLI scaffold              │  │
                         │  Bundle layout, CI/CD wiring,   │  │
                         │  UC schema + volume, AGENTS.md  │  │
                         └─────────────────────────────────┘  │
                                                              ▼
                                                    ┌───────────────────┐    ┌──────────────┐
                                                    │  Scaffold         │    │  CI/CD       │
                                                    │  .agentops-stacks │──▶│  workflows   │
                                                    │  /manifest.yml    │    │  per platform│
                                                    └───────────────────┘    └──────────────┘
                                                              ▲
                         ┌─────────────────────────────────┐  │
   Claude Code      ─▶  │  agentops-stacks plugin         │ ─┘
   Cursor / Genie       │  Portable SKILL.md skills       │
                        │  Authoring, review, proposal,   │
                        │  lifecycle pattern application  │
                        └─────────────────────────────────┘
```

**Reading the diagram:**

1. The **DAB template** is the canonical path. A user runs `databricks bundle
   init` and gets a complete scaffold with no plugin or assistant required.
2. The **agentops-stacks plugin** is portable across coding assistants — same
   SKILL.md content, surfaced through whichever assistant the developer uses.
   The plugin operates on an existing scaffold to apply production patterns,
   review changes against project priorities, and propose next steps.
3. Both channels write to the shared scaffold contract,
   `.agentops-stacks/manifest.yml`. The contract records which patterns have
   been applied so CI/CD and tooling can read project state without needing
   to know how the scaffold was created.
4. CI/CD workflows are scaffolded once and operate identically regardless of
   which channel created the project.

Key principles:
- Both channels produce the same scaffold shape. CI/CD doesn't know or care
  which channel created it.
- The plugin is optional. The DAB template stands on its own.
- The manifest is the contract — adding a new channel (e.g., a future
  drag-and-drop interface) means writing the same manifest, not changing the
  scaffold consumers.

## Production Patterns

The scaffold ships structural pieces only. Production patterns — eval gates,
governance posture, monitoring, feedback loops — are applied as the solution
develops, not pre-installed. Each pattern is a small set of additions to an
existing scaffold (configs, code, docs) that the CI/CD wiring is already
prepared to consume.

The pattern set is grounded in Big Book Pattern 1 baseline and Veena's Field
Guide:

- **Evaluation** — three-tier testing (Tier 1 unit, Tier 2 integration with
  mocked + real LLM, Tier 3 system eval via `mlflow.genai.evaluate()`),
  golden dataset lifecycle (production trace capture → SME review → version-
  compared eval), eval gates config consumed by CD.
- **Governance posture** — per-pattern security and compliance documentation,
  DASF 3.0 control mapping artifact, data flow inventory.
- **Monitoring** — production tracing in MLflow/OTel format, AI/BI dashboard
  over traces (quality, latency, cost, volume), cost-tracking via token
  usage.
- **Feedback loops** — end-user feedback UI writing to a Delta feedback
  table, SME labeling-session workflow, batch inference for offline
  evaluation against production traffic.

Per-pattern documentation lives alongside each pattern as it's defined.

### Deliberate deltas above the Big Book baseline

These are commitments agentops-stacks makes beyond the current Big Book draft.
The Big Book is authoritative once finalized; until then, each delta is a
temporary position that either folds into the Big Book or is dropped if the
finalized Big Book takes a different direction. Each one is documented so the
team can track it as the Big Book evolves:

- **Minimum AI Gateway posture on every deployed agent** (rate limit +
  content filter). Per Design Priority 5.
- **DASF 3.0 posture aggregation as a CD artifact** — generated by reading
  each applied pattern's compliance metadata.
- **Prompt versioning required** alongside model versioning (MLflow Prompt
  Registry for non-PHI; Delta-backed fallback for PHI).
- **Structured observability mandated** — MLflow / OTel formats, no custom
  log schemas (anti-pattern). Forward-compatible with Lakewatch.
- **Three-tier testing as canonical vocabulary** — every eval/test artifact
  identifies its tier.
- **Custom scorer slot as a deliberate empty artifact** — projects can ship
  with built-in scorers only; the slot reserves location for custom
  `@scorer` functions without restructuring.

## Governance & Platform Constraints

From the Databricks AI Governance Strategy (March 2026) and team sync
decisions.

- **UC securables are expanding over summer 2026.** How we reference securable
  objects (agents, models, tools, skills) will need to evolve. Avoid
  hardcoding current resource type assumptions where possible.
- **AI Gateway is the governance enforcement layer.** Design guardrails around
  AI Gateway configuration — not just content filtering but agent behavioral
  restrictions as the platform evolves.
- **Tool Gateway / MCP governance is coming.** MCP servers will be first-class
  UC securables with identity propagation. Pattern documentation should cover
  Tool Gateway integration once available.
- **Structured observability, not custom schemas.** Monitoring patterns emit
  structured logs compatible with Lakewatch (platform AI-optimized SIEM, in
  development). Use MLflow/OTel trace formats, don't invent custom log
  schemas.
- **External agents are a future hosting pattern.** No first-class UC object
  yet, but the current pattern (UC connections + registry table + pyfunc
  wrapper + centralized telemetry) works with GA building blocks. Eval and
  monitoring patterns should work against any agent that emits standard
  traces, not just Databricks-hosted agents.
- **Identity propagation (OBO)** is outside scope to implement but is a
  customer-action item — document what identity model each pattern assumes.
- **Cost tracking** as a default when agent patterns are applied (MLflow
  token logging). A full cost assessment tool is a future add-on.
