# Examples

Reference solutions that demonstrate how to apply production patterns to a real
agent inside an agentops-stacks scaffold. Examples are **optional and
separate** — the base scaffold ships nothing example-like, and adopting an
example is a deliberate user choice.

## Why examples are separate (not embedded)

Earlier MLOps/AgentOps stacks templates embedded a sample solution directly in
the generated bundle. That approach had two recurring problems:

- **Hard to maintain.** Sample code and template code drifted apart over time.
- **Hard to adapt.** Users had to identify and remove sample-specific files
  before adapting the scaffold to their actual use case.

agentops-stacks separates the two: the scaffold is clean, and examples
live here as standalone reference projects the user can adopt selectively.

## What each example contains

Each example is a complete, checked-in scaffold + a specific solution +
the production patterns applied against it:

- `databricks.yml`, `resources/`, CI/CD workflows — same shape as `bundle init`
  produces
- `src/` — minimal solution code (deliberately small)
- `evaluation/`, `governance/`, `monitoring/`, `feedback/` — production
  patterns applied to this specific solution
- `README.md` — what this example demonstrates and the recipe to reproduce it

Examples are the development testbed for production patterns: the pattern
contracts in [`projectdocs/patterns/`](../projectdocs/patterns/) describe
*what* each pattern is, and the examples here are the worked instances.

## How to adopt an example

Two paths, depending on whether you have the agentops-stacks plugin
installed:

**Without the plugin (manual):**
1. Run `databricks bundle init` against the template as you normally would
   (see the [repo README](../README.md)).
2. Copy the example's `src/`, `evaluation/`, etc. into your project.
3. Adjust references (catalog names, model URIs, dataset paths) to match your
   workspace.

**With the agentops-stacks plugin (future):**
A `/apply-example <name>` command copies and adapts the example's pattern
files into your existing scaffold.

## Current examples

| Example | What it demonstrates | Patterns applied |
|---------|----------------------|------------------|
| [`hello-agent/`](hello-agent/) | Minimal pyfunc agent registered to UC — the simplest closed loop | Evaluation |

More examples will land as the pattern set grows.
