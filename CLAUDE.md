# AgentOps Stacks

Composable DAB-based project generation for AI solutions on Databricks. Users
assemble agent apps, evaluation gates, data pipelines, and operational components
into a Databricks Asset Bundle, then deploy through CI/CD with eval-gated promotion.

## Design Priorities (in order)

1. **Flexible, extendable, composable model for building AI solutions.** The component
   architecture is the core value proposition. If a choice makes one component easier
   but makes composition harder, composition wins.

2. **Opinionated evaluation gates.** Every component that can be evaluated ships with
   evaluation built in. The default is eval-on, not eval-off. Where evaluation isn't
   yet possible (e.g., pending SDK support for Genie Benchmarks or KA Guidelines),
   include a stub that documents what will be evaluated and exits cleanly.

3. **Closed-loop operations, not demos.** Every operational capability must close the
   loop back to development action. Production eval results feed back as new eval
   dataset entries. User/SME feedback becomes annotation candidates. Monitoring alerts
   map to runbooks. If a component only demonstrates a capability without connecting
   it to the feedback loop, it's incomplete.

4. **Challenge assumptions at every step.** After completing a design decision or
   implementation step, surface what's still uncertain, what could break the
   assumption, or what the next decision depends on. Every review should end with
   "what are we missing?"

5. **Security built into every component.** For each component, document: what data
   flows through it, where that data is stored or logged, and what compliance
   implications that creates.

   Key principles:
   - **No lazy defaults.** UC-governed resources, scoped credentials, least-privilege
     permissions, and workspace-boundary data flows by default.
   - **Practical security documentation per component.** What to configure, what to
     restrict, what to watch for. Written for the deployer, not the compliance auditor.
   - **DASF 3.0 posture visibility.** Each component documents which DASF practices it
     implements by default, which require customer configuration, and which are out of
     scope.
   - **GA vs preview diligence.** Model: MLflow 3 core is HIPAA-supported under CSP,
     but Prompt Registry (Beta) is not listed under "Supported preview features" — so
     non-PHI only. Apply this level of scrutiny to every component.

6. **Compatible with ai-dev-kit, not dependent on it.**
   [ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit) provides MCP
   servers and skills for creating and managing individual Databricks resources. This
   project is the operational framework above it: project composition, lifecycle
   (CI/CD, eval gates, promotion), operational loops (monitoring, HITL feedback),
   and compliance posture. Build new ai-dev-kit skills for the operational domain.
   Don't rebuild resource creation that ai-dev-kit already handles. But every workflow
   must be completable without ai-dev-kit — through the CLI or by editing DAB files
   directly. ai-dev-kit is an accelerator, not a prerequisite.

## Standing Requirements

- **DAB direct engine only.** All generated `databricks.yml` files include
  `bundle: engine: direct`. The legacy Terraform-backed engine is not supported.
  Deploy commands use plain `databricks bundle deploy -t <target>` — the engine
  setting in `databricks.yml` handles engine selection. Do not pass engine flags
  on the CLI.

- **Declarative DAB resources over notebook-created resources.** If a resource is a
  first-class DAB resource type, define it in `databricks.yml`. Notebooks only create
  resources DAB doesn't yet support. Document why so it can be migrated when support
  lands. Reference: https://docs.databricks.com/aws/en/dev-tools/bundles/resources
  Known notebook-required: Vector Search index (not yet a DAB resource type).
  <!-- Add others here as discovered. Remove when DAB support lands. -->

- **One DAB = one deployment unit.** Single component or multi-component — both valid.
  Cross-DAB dependency orchestration is out of scope.

- **Concise, actionable documentation.** What this is, what to configure, how to
  deploy, relevant links. Assume Databricks and CI/CD familiarity. No editorializing.

## Architecture

### Target Solution Architecture

The production pattern is a three-environment lifecycle with eval-gated promotion:

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

This scales along two axes: single/multi-agent and single/multi-account. Multi-account
variants add Data Sharing between accounts. Multi-agent variants add per-agent workflow
blocks and routing.

### Tooling Architecture

Three paths to populate a DAB, all producing the same output structure:

- **A. Quick-Start Examples** — imported from `databricks/app-templates`. Fastest path,
  minimal agent app, no ops scaffolding.
- **B. Solution Templates** — pre-assembled from components for common production
  patterns (RAG, document intelligence, process automation).
- **C. Component Assembly** — start with a blank DAB, add discrete modules one at a
  time. Maximum flexibility.

Three user interfaces access all three paths: CLI tools, drag-and-drop app builder,
and coding agent skills (Claude Code, Cursor, etc.). All produce a Databricks Asset
Bundle that feeds into CI/CD workflows for dev/staging/prod promotion.

Key principles:
- Components are the atomic unit. Solution templates are frozen combinations.
- All paths produce the same DAB structure. CI/CD doesn't know how it was assembled.
- Paths can be mixed: start from a template, add individual components to fill gaps.

### Component Specification

Each component is defined by **DAB artifacts** (config, workflows, code) and a
**component manifest** (`component.md`) with structured metadata.

Component manifest covers: name, description, category, dependencies, platform
resources (creates/requires), DAB variables, data flows, compliance metadata
(feature status, HIPAA support, security defaults, customer actions), documentation
links, and examples.

Component directory structure:
```
components/<component_name>/
├── component.md           ← Manifest + documentation
├── databricks.yml         ← DAB resource snippet
├── resources/             ← Job workflow definitions (optional)
├── notebooks/             ← Databricks notebooks (optional)
├── src/                   ← Python source code (optional)
└── app.yaml               ← App runtime config (optional)
```

Manifests are consumed by CLI tools, the drag-and-drop app, coding assistant skills,
and pre-flight validation.

## Governance & Platform Constraints

From the Databricks AI Governance Strategy (March 2026).

- **UC securables expanding (summer 2026).** Avoid hardcoding current resource type
  assumptions.
- **AI Gateway is the governance enforcement layer.** Design guardrails around it.
- **Tool Gateway / MCP governance coming.** MCP servers will be UC securables with
  identity propagation. Document integration path.
- **Structured observability.** Use MLflow/OTel trace formats. No custom log schemas.
  Compatible with Lakewatch (platform AI-optimized SIEM, in development).
- **External agents are a future hosting pattern.** Current pattern: UC connections +
  registry table + pyfunc wrapper. Eval/monitoring should work against any agent that
  emits standard traces.
- **Identity propagation (OBO)** — document in component manifests as customer_actions.
- **Cost tracking** as a default in agent components (MLflow token logging).

## Validation

- `databricks bundle validate` must pass after any change.
- `databricks bundle deploy --target dev` is the deployment command. The direct
  engine is configured in `databricks.yml` — do not use the legacy Terraform engine.
- After adding a component, verify that `bundle validate` still passes and that
  existing components are not broken.
