# AgentOps Stacks Components

Composable building blocks for Databricks Asset Bundle projects. Each component is a
self-contained set of DAB configuration, code, and metadata that can be added to a
generated project via the setup script.

This repo-root `components/` directory is the development source. The template copy
at `template/{{.input_root_dir}}/components/` is included in every generated project
so the setup script can read components locally with no network dependency. Keep both
in sync — changes here should be copied to the template directory.

## Component structure

```
components/<name>/
├── component.md           # Manifest (YAML frontmatter) + documentation
├── agent_server/          # Source code (optional, varies by component)
├── resources/             # DAB resource definitions (optional)
├── scripts/               # Setup-time or runtime scripts (optional)
└── ...
```

## Manifest format

Each component has a `component.md` with YAML frontmatter that the setup script
reads to understand dependencies, file operations, and project modifications.

See any component's `component.md` for a working example.

## How the setup script uses components

1. Reads the manifest frontmatter to resolve dependencies
2. Copies the component's files into the project (`copies` field)
3. Applies declared modifications to existing project files (`modifies` field)
4. Fetches external sources if declared (`external_sources` field)
5. Runs `databricks bundle validate` to confirm the result
