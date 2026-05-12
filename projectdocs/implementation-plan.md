# AgentOps Stacks — Implementation Plan

**Status:** Active
**Last Updated:** 2026-05-12

Design principles, architecture, and source-of-truth references are in
[design-and-architecture.md](design-and-architecture.md). This document tracks
where v2 stands and what's next. Detailed implementation history lives in the
git log and PR descriptions.

## Status

v2 was a deliberate reset on 2026-05-11 (commit `cd7822a`) that dropped the
component-assembly model from earlier work and re-anchored the project on two
channels — a DAB template (canonical) and an agentops-stacks plugin (planned).
Both produce or operate on the same scaffold, with `.agentops-stacks/manifest.yml`
as the shared contract.

The DAB template channel is functional end-to-end. The plugin channel and all
production patterns are not yet implemented.

| Channel / Pattern | State |
|---|---|
| DAB template (scaffold) | Functional; validated via `bundle init` + `bundle validate` + `bundle deploy --target dev` |
| agentops-stacks plugin | Planned, not started |
| Evaluation pattern | Not started |
| Governance posture pattern | Not started |
| Monitoring pattern | Not started |
| Feedback loops pattern | Not started |

## Channel A: DAB template

### What ships today

- `databricks.yml` with `bundle: engine: direct`, three-environment targets
  (dev / staging / prod), per-environment UC catalog defaults.
- Bundle resources: UC schema, managed volume for artifacts, MLflow experiment
  configured to land artifacts in the volume.
- CI/CD workflow templates for four platforms: GitHub Actions, GitHub Actions
  for GitHub Enterprise Servers, GitLab, and Azure DevOps. PR validates;
  merge to `main` deploys to staging; tag `v*` deploys to prod.
- Cloud auth wired per platform: Azure (service principal), AWS and GCP
  (token-based).
- `pyproject.toml`, `.env.example`, `.gitignore`.
- `AGENTS.md` — tool-agnostic conventions for coding assistants.
- `docs/setup.md` — end-to-end configuration guide for UC catalogs, CLI
  profiles, and CI/CD credentials per cloud and platform.

### What's validated

- `databricks bundle init` against the template produces a project that passes
  `databricks bundle validate` and `databricks bundle deploy --target dev`
  against a live workspace.
- CI/CD workflows render correctly for all four platforms (validated in
  template tests, not yet exercised in a live CI run for v2).

### What's next

- **Vector Search index pattern.** Not a first-class DAB resource type yet; will
  ship as a notebook-based creation with documentation about why and a marker
  to migrate when DAB support lands.
- The four production patterns below.

## Channel B: agentops-stacks plugin

Planned. Packages the same guidance the DAB template ships, plus interactive
authoring help (apply patterns, review against priorities, propose next steps).

Scope at a high level:

- Portable SKILL.md content usable across coding assistants — Claude Code,
  Cursor, Genie Code.
- Installer pattern mirrors ai-dev-kit's, per the precedent established in
  earlier work.
- Operates on the shared scaffold contract (`.agentops-stacks/manifest.yml`)
  so plugin behavior stays consistent with the CLI workflow.

Detailed plugin scope (skill list, installer mechanics, cross-assistant
testing) will be planned as a separate document when the plugin work starts.

## Production Patterns Roadmap

Patterns are applied as the solution develops, not pre-installed. Each pattern
is one PR's worth of additions to an existing scaffold (configs, code, docs)
that the CI/CD wiring is already prepared to consume.

The pattern set is grounded in the Big Book of Agent Ops Pattern 1 baseline
and Veena's Field Guide. All four are not yet started; the order below is the
expected delivery sequence.

### 1. Evaluation

- Three-tier testing scaffold (Tier 1 unit, Tier 2 integration with mocked
  and real LLM sub-tiers, Tier 3 system eval via `mlflow.genai.evaluate()`).
- Eval gate config (`evaluation/thresholds.yml`) consumed by CD with blocking
  and warning thresholds; gate logic (`evaluation/gate.py`) that CI workflows
  auto-detect.
- Golden dataset lifecycle (production trace capture → SME review → version-
  compared evaluation) with the canonical row schema (`inputs`,
  `expected_response`, `expected_facts`, `tags`).
- Two distinct flows in scope:
  - **Automated eval gates** in CI/CD — block promotion on failure.
  - **HITL feedback** — async; produces eval dataset entries and prompt
    revisions that feed the next iteration cycle.

### 2. Governance posture

- Per-pattern security documentation (`governance/posture.md`) capturing GA
  vs preview status, data flows, compliance implications.
- Data flow inventory (`governance/data_flows.md`).
- DASF 3.0 control mapping artifact, generated during CD by aggregating each
  applied pattern's compliance metadata.
- Prod-promotion workflow checks for presence of these artifacts.

### 3. Monitoring

- Production tracing wired in MLflow / OTel format; no custom log schemas.
- AI/BI dashboard over production traces (quality, latency, cost, volume).
- Cost-tracking signal — token usage captured in traces.
- Forward-compatible with Lakewatch as that platform matures.

### 4. Feedback loops

- End-user feedback UI writing to a Delta feedback table linked by trace ID.
- SME labeling-session workflow targeting traces where LLM judges are
  uncertain; outputs feed golden dataset curation.
- Batch inference in production for offline evaluation against a production
  traffic sample.

## Open Questions

- **CI eval gate logic not yet proven against a live target.** The four CI
  platforms render the gate hook, but the gate step itself fires no work today
  (patterns not applied yet). First live exercise will accompany the
  evaluation pattern delivery.
- **Genie Code git constraint.** Genie Code cannot create remotes, clone, or
  push; git is user-driven via the workspace Repos UI. All scaffolding flows
  must treat repo + clone as a prerequisite rather than something the tool
  performs.
- **ai-dev-kit cherry-pick scope.** Skills worth importing (eval, MLflow
  tracing, related) are identified but not yet imported into the plugin
  surface. Decision is to import skills only, not the ai-dev-kit MCP server.
- **MCP server evaluation.** No established Databricks eval mechanism for MCP
  servers (tool call correctness, schema compliance) exists yet. Track as the
  evaluation pattern matures.
- **Model Serving deployment-cascade race condition.** Marked resolved
  upstream but untested. Deferred while focus is on the scaffold + plugin
  rollout.
- **Big Book finalization.** The Big Book of Agent Ops is currently a draft.
  When it finalizes, re-evaluate the deliberate deltas documented in
  `design-and-architecture.md` — fold into the Big Book where the draft has
  caught up, or drop where the finalized direction differs.

## Reference: pre-v2 history

The component-assembly model — `components/<name>/` directories,
`component.md` manifests, `install_components()` setup script, per-component
DAB snippets — was dropped in the v2 reset. The historical state of that work
lives on the `agentops-stacks-rebase` branch.

The pre-v2 work produced two functional components (`agent_app`,
`mcp_server`) and validated that CLI-driven component stitching was workable.
The decision to drop the model was driven by ownership-boundary
considerations (see Design Priority #1 in
[design-and-architecture.md](design-and-architecture.md)) — coding assistants
and ai-dev-kit already own the component-creation surface, and re-implementing
it inside agentops-stacks competed with those tools instead of complementing
them. The v2 architecture preserves the structural pieces that proved
valuable (the scaffold, CI/CD wiring, UC conventions) and delegates
component creation to the integration layer.
