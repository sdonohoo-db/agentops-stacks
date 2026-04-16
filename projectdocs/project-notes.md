# AgentOps Stacks — Project Notes

Context, decisions, and action items that inform the project but are not build instructions.
For the build plan, see `CLAUDE.md`.

## Tim Lortz Sync — 2026-04-08

Attendees: Tim Lortz, Alex Baur, Scott Donohoo, Veena Ramesh, Robert Mosley

Full call notes and transcript:
- [Original (Scott's copy)](https://docs.google.com/document/d/1lz03w_tSrJlyS6XWzZrM2iU71Ot9R34AtLbbPIi3LF8/edit?tab=t.38qsrh1yl4o1)
- [Backup copy](https://docs.google.com/document/d/1uj-LsX0RhQxOUx-4nyjYxBYOuy4GgNoeISDNo5IuliI/edit?tab=t.38qsrh1yl4o1)

### Decisions

1. **Fully decouple from MLOps Stacks.** AgentOps Stacks is an entirely separate
   template, no longer constrained by MLOps Stacks' structure.

2. **Agents and resources are loosely coupled.** Agents are independent of their
   resources (vector indexes, tools, etc.). Resources should be available across
   multiple agents. Agent-centered, not all-encompassing.

3. **Evaluation and monitoring are mandatory, not optional.** Strongest consensus
   point. Customers consistently neglect evaluation. "Without CI/CD this is a toy"
   — direct customer feedback.

4. **Evaluation is its own ops story ("Eval Ops").** Separate from agent ops. Eval
   has its own CI/CD: new traces come in, monitoring flags issues, humans review
   traces before adding to eval datasets, eval dataset improves, devs improve the
   agent against the benchmark. Two-motion cycle: people improve the benchmark,
   developers improve the agent. (Veena's proposal, Robert and Tim agreed.)

5. **DABs as first-class deployment, with other avenues alongside.** DABs should
   always be available as the ready-to-go deployment path. Other options (AI devkit,
   etc.) can coexist but DABs are the primary.

6. **Apps deployment is the pivot.** Databricks Apps are well supported by DABs now.
   Model serving endpoint deployment was previously problematic as a first-class
   resource.

7. **Must be workshopable.** Tim wants this distilled into something that can be
   positioned and guided through with customers and partners. CI/CD automation is
   the priority for the workshop format.

### Action Items

- Tim shared the AI governance strategy doc:
  https://docs.google.com/document/d/1xKbWaJAjjvILLAqUy7E72SwyyYX1siuCYZDlw-MpOYg/edit?tab=t.0#heading=h.m13y5zwbybmt
- Tim to share CI/CD automation notes
- Tim to establish a direct line to R&D for roadmap input on Agent Bricks and DABs
- Core team (Alex, Scott, Veena) to present rough cut at ML-SME meeting (target May 2026)
- Core team to distill into workshop format for field and partner use
- Scott has two customers waiting on an agentops workshop — immediate test bed

### Key Signals

- UC securables are changing over the summer — how we reference securable objects will
  need to evolve. Design for this.
- Product is still thrashing on AI governance strategy but solidifying. The framework
  should be strongly opinionated about the governance primitives as they land.
- Robert drew the parallel between evaluation and unit testing adoption in the 90s —
  took decades for unit tests to become standard practice. This framework can
  accelerate that adoption curve for AI eval.
- Even the simplest agent is more complex ops-wise than the most complex ML use case
  (Veena's point). A feature store was the ceiling for ML; agents use 2-3+ components
  by default.
- Partners won't sell without CI/CD. Customers called the previous version "a toy"
  without it.

## AI Governance Strategy Alignment

Tim shared the product AI governance strategy doc (March 2026, approved by exec staff):
https://docs.google.com/document/d/1xKbWaJAjjvILLAqUy7E72SwyyYX1siuCYZDlw-MpOYg/edit

The strategy defines six governance surface areas and sequences platform investment.
Our plan is largely consistent. Full analysis below; actionable constraints extracted
into CLAUDE.md under "Governance & Platform Constraints."

**Where we align:**

1. **All AI objects governed in UC** (agents, models, tools, skills). Reinforces our
   standing requirement to use declarative DAB resources backed by UC. UC securables
   are expanding over summer — our resource references will need to evolve.

2. **AI Gateway is the governance enforcement layer** (their #1 priority). Guardrails,
   custom policies, UC-modeled endpoints. Guardrails will be a component a customer
   can add to their solution.

3. **Tool Gateway and MCP governance** (their #2 priority). MCP servers as first-class
   UC securables with identity propagation.

4. **Observability and auditability** across all AI assets. Our end-to-end pattern
   includes monitoring as a core requirement (closed-loop ops).

**Gaps to track:**

1. **External agent registration** — "commandment #1" per Ali Ghodsi. No first-class
   external-agent UC object exists yet. Current pattern uses UC HTTP/MCP connections +
   registry table + optional pyfunc wrapper + centralized telemetry.
   [Pattern doc](https://docs.google.com/document/d/1NFGJWfVbbat5fNzuKNIQzPQLMvP5fh-rYojBbN4NLxw/edit)

2. **Identity propagation and OBO** — agents inherit user identity without repeated
   OAuth. Outside our scope to implement but a `customer_actions` item in manifests.

3. **Cost assessment** — per-agent cost tracking is a competitive gap. Redux had cost
   tracking via MLflow token logging, which should carry forward.

## Delivery Targets

- **ML-SME presentation:** target May 2026, rough cut of the composability demo + RAG template
- **Customer workshops:** Scott has two customers waiting on an agentops workshop — use the reviewable milestone as the first workshop test bed
- **Workshop format:** Tim wants CI/CD automation as the priority for workshop content
- **Partner readiness:** partners won't sell without CI/CD, so the fast track must include it
