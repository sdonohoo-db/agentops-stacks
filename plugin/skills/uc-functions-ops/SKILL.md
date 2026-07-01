---
name: uc-functions-ops
description: Operate and troubleshoot the UC Functions tools component in an AgentOps Stacks project — register new functions, update EXECUTE grants, list available functions, re-run the registration job. Use when the user needs to add, update, or grant access to UC functions used by their agent.
---

# uc-functions-ops — UC Functions Operations

Covers day-to-day operations for the `resources/uc_function_registration.yml` component: adding new function definitions, re-registering after changes, and managing EXECUTE grants for the agent's service principal.

## When to use

- "add a new UC function tool"
- "my agent can't call the UC function"
- "re-register UC functions after I changed the definition"
- "grant execute permission to the app service principal"
- "list what UC functions are registered"
- "the function registration job failed"

## Key resources in the project

| File | Purpose |
|---|---|
| `resources/uc_function_registration.yml` | DAB job that runs the registration notebook |
| `src/components/tools/registry.py` | Notebook: discovers `definitions/`, registers functions, grants EXECUTE |
| `src/components/tools/definitions/` | Function definitions (`.py` or `.sql` per function) |
| `src/agents/<name>/tools.py` | Agent tool selection — loads UC functions via `UCFunctionToolkit` |

---

## Operations

### 1. List registered UC functions

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

catalog = "<catalog>"
schema = "<schema>"

functions = w.functions.list(catalog_name=catalog, schema_name=schema)
for f in functions:
    print(f.full_name)
```

Or in SQL:
```sql
SHOW FUNCTIONS IN <catalog>.<schema>;
DESCRIBE FUNCTION <catalog>.<schema>.<function_name>;
```

### 2. Add a new Python function

Create a new file in `src/components/tools/definitions/`. The file name becomes the function name.

**Requirements:**
- File name must be a valid Python identifier (e.g. `get_customer_info.py`)
- Define one callable with the same name as the file
- Add type hints on all parameters and return type
- Add a Google-style docstring (used as the LLM tool description)

```python
# src/components/tools/definitions/get_customer_info.py

def get_customer_info(customer_id: str) -> dict:
    """Retrieve customer information by ID.

    Args:
        customer_id: The unique customer identifier.

    Returns:
        A dict with keys: name, email, plan, created_at.
    """
    # TODO: replace with real lookup
    return {"name": "Example", "email": "ex@example.com", "plan": "enterprise"}
```

Then re-run registration (step 4).

### 3. Add a new SQL function

Create a `.sql` file in `src/components/tools/definitions/`. Use `${var.catalog}` and `${var.schema}` as placeholders — the registry notebook substitutes them.

```sql
-- src/components/tools/definitions/summarize_orders.sql
CREATE OR REPLACE FUNCTION ${var.catalog}.${var.schema}.summarize_orders(
  customer_id STRING COMMENT 'Customer identifier'
)
RETURNS STRING
COMMENT 'Return a plain-text summary of the customer''s recent orders.'
LANGUAGE SQL
RETURN (
  SELECT CONCAT('Total orders: ', COUNT(*))
  FROM ${var.catalog}.${var.schema}.orders
  WHERE customer_id = summarize_orders.customer_id
);
```

Then re-run registration (step 4).

### 4. Re-register functions (run the job)

After adding or editing definitions, trigger the registration job:

```bash
# Via bundle (runs the DAB job)
databricks bundle run -t dev uc_function_registration
```

Or manually via CLI:
```bash
databricks jobs run-now --job-id <job-id-from-databricks.yml>
```

Monitor progress:
```bash
databricks runs get --run-id <run-id>
databricks runs get-output --run-id <run-id>
```

The job:
1. Discovers all `.py` and `.sql` files in `definitions/`
2. Registers (or replaces) each function in `<catalog>.<schema>`
3. Grants `EXECUTE` to the app service principal (if `app_sp` is set)

### 5. Grant EXECUTE to the app service principal

The app SP needs `EXECUTE` on each function it calls. The registration job handles this if `app_sp` is set.

**To set the app SP in the registration job:**

In `resources/uc_function_registration.yml`, fill in the `app_sp` parameter:
```yaml
base_parameters:
  catalog: ${var.catalog}
  schema: ${var.schema}
  app_sp: "app-sp-client-id-here"   # ← set this
```

Then redeploy + re-run:
```bash
databricks bundle deploy -t dev
databricks bundle run -t dev uc_function_registration
```

Or grant manually:
```sql
-- Grant EXECUTE to the app service principal
GRANT EXECUTE ON FUNCTION <catalog>.<schema>.<function_name> TO `<app-sp-client-id>`;

-- Verify
SHOW GRANTS ON FUNCTION <catalog>.<schema>.<function_name>;
```

### 6. Update an existing function definition

Edit the file in `definitions/` and re-run registration. The registry uses `replace=True` for Python functions and `CREATE OR REPLACE` for SQL — no manual deletion needed.

### 7. Remove a function

```sql
DROP FUNCTION <catalog>.<schema>.<function_name>;
```

Also delete the corresponding `.py` or `.sql` file from `definitions/` to prevent it from being re-created on the next registration run.

### 8. Verify the agent can call the function

Check `src/agents/<name>/tools.py` — it should include the UCFunctionToolkit for loading registered functions:

```python
from unitycatalog.ai.langchain.toolkit import UCFunctionToolkit

def get_tools():
    toolkit = UCFunctionToolkit(function_names=[
        "<catalog>.<schema>.*"   # load all, or list specific functions
    ])
    return toolkit.tools
```

Test that the tools are discovered without starting the full agent:
```python
from tools import get_tools
tools = get_tools()
for t in tools:
    print(f"{t.name}: {t.description[:80]}")
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `No definitions found` in job output | Wrong `definitions/` path | The job looks relative to the notebook path — verify `registry.py` is in `src/components/tools/` |
| `SKIP: file.py — no callable named 'file' found` | Function name doesn't match file name | Rename the function or rename the file to match |
| Function registered but agent can't call it | Missing EXECUTE grant on app SP | Grant EXECUTE (step 5) |
| `FunctionNotFound` at agent runtime | Function not registered or wrong catalog/schema | Run `SHOW FUNCTIONS IN <catalog>.<schema>` to verify |
| Tool description is wrong | Docstring outdated | Update docstring and re-register (step 4) |
| Registration job fails with `existing_cluster_id not set` | Job resource needs a cluster | Set `existing_cluster_id` in `uc_function_registration.yml` or add a `job_cluster_key` |
| `SQL function already exists` error | `CREATE FUNCTION` instead of `CREATE OR REPLACE` | Use `CREATE OR REPLACE FUNCTION` in `.sql` files |

## Function naming convention

Functions registered in Unity Catalog are named `<catalog>.<schema>.<file_stem>`. Keep file names lowercase with underscores (e.g. `get_weather.py` → `<catalog>.<schema>.get_weather`). The LLM sees the function name and docstring as the tool description — make both descriptive.

## Updating the agent tool list

When you add or remove functions, also update `src/agents/<name>/tools.py` if you're selecting specific functions by name (rather than loading all with `*`). Redeploy the app:

```bash
databricks bundle deploy -t dev
```

No restart needed — the App picks up the new tools on the next invocation.
