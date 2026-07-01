---
name: lakebase-ops
description: Operate and troubleshoot the Lakebase memory component in an AgentOps Stacks project — check connection health, refresh credentials, inspect or clear checkpointer tables, manage the Postgres schema. Use when the user's agent is having memory/persistence issues.
---

# lakebase-ops — Lakebase Memory Operations

Covers day-to-day operations for the `resources/lakebase.yml` component: the Lakebase Postgres instance used as a LangGraph checkpointer for agent conversation memory.

## When to use

- "agent lost conversation history"
- "lakebase connection failed"
- "token expired" or "authentication error connecting to postgres"
- "how do I clear memory for a user?"
- "inspect what's stored in the checkpointer"
- "the checkpointer isn't working"

## Key resources in the project

| File | Purpose |
|---|---|
| `resources/lakebase.yml` | DAB resource: Lakebase instance + catalog |
| `src/agents/<name>/graph.py` | `get_async_checkpointer()` — credential refresh + table setup |
| `src/agents/<name>/app.yaml` | `LAKEBASE_INSTANCE`, `LAKEBASE_HOST`, `LAKEBASE_DB` env vars |

The instance is named `<project>-memory` and the catalog is `<project>_memory`. The checkpointer uses the `default` database.

---

## Operations

### 1. Check instance health

```bash
# List instances
databricks database-instances list

# Get specific instance
databricks database-instances get --name <project>-memory
```

In Python:
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

instance = w.database.get_database_instance(name="<project>-memory")
print(instance.state)       # AVAILABLE / STARTING / STOPPING / STOPPED / FAILED
print(instance.read_write_dns)  # host to use in connection string
```

### 2. Test database connectivity

Credentials are short-lived OAuth tokens. Generate a fresh one and verify the connection:

```python
from databricks.sdk import WorkspaceClient
import psycopg

w = WorkspaceClient()
user = w.current_user.me().user_name
cred = w.database.generate_database_credential(instance_names=["<project>-memory"])

host = "<value of LAKEBASE_HOST from app.yaml>"
conn_str = f"postgresql://{user}:{cred.token}@{host}:5432/default?sslmode=require"

with psycopg.connect(conn_str) as conn:
    row = conn.execute("SELECT version()").fetchone()
    print(row[0])
print("Connection OK")
```

If this fails, see the Troubleshooting section below.

### 3. Inspect checkpointer tables

LangGraph's `AsyncPostgresSaver` creates these tables on first call to `checkpointer.setup()`:

- `checkpoints` — one row per (thread_id, checkpoint_id)
- `checkpoint_blobs` — serialized graph state
- `checkpoint_writes` — pending writes (cleared after commit)

```python
# (reuse conn from step 2)
with psycopg.connect(conn_str) as conn:
    # List threads with saved state
    rows = conn.execute(
        "SELECT thread_id, MAX(checkpoint_id) AS latest FROM checkpoints GROUP BY thread_id ORDER BY latest DESC LIMIT 20"
    ).fetchall()
    for r in rows:
        print(r)

    # Count rows per table
    for t in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {n} rows")
```

### 4. Clear memory for a thread

To reset a conversation thread (e.g. for a specific user session):

```python
thread_id = "user-123-session-abc"

with psycopg.connect(conn_str, autocommit=True) as conn:
    conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
    conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
    conn.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))

print(f"Cleared memory for thread {thread_id}")
```

### 5. Clear all memory (reset checkpointer)

**Destructive.** Use in dev/staging only.

```python
with psycopg.connect(conn_str, autocommit=True) as conn:
    conn.execute("TRUNCATE checkpoint_writes, checkpoint_blobs, checkpoints")
print("All checkpointer tables cleared")
```

### 6. Verify env vars in `app.yaml`

The checkpointer in `graph.py` reads three env vars:

```yaml
# src/agents/<name>/app.yaml
env:
  - name: LAKEBASE_INSTANCE
    value: <project>-memory            # instance name (for credential generation)
  - name: LAKEBASE_HOST
    value: <read-write DNS from instance.read_write_dns>
  - name: LAKEBASE_DB
    value: default                      # optional, defaults to "default"
```

Get the host:
```bash
databricks database-instances get --name <project>-memory --output json | jq .read_write_dns
```

After updating `app.yaml`:
```bash
databricks bundle deploy -t dev
```

### 7. Force checkpointer table creation

If the agent starts but the checkpointer tables don't exist yet (e.g. fresh instance):

```python
import asyncio
from databricks.sdk import WorkspaceClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection

async def setup():
    w = WorkspaceClient()
    user = w.current_user.me().user_name
    cred = w.database.generate_database_credential(instance_names=["<project>-memory"])
    host = "<LAKEBASE_HOST>"
    conn_str = f"postgresql://{user}:{cred.token}@{host}:5432/default?sslmode=require"
    conn = await AsyncConnection.connect(conn_str, autocommit=True, prepare_threshold=0)
    checkpointer = AsyncPostgresSaver(conn)
    await checkpointer.setup()
    print("Checkpointer tables created")

asyncio.run(setup())
```

### 8. Resize the instance

In `resources/lakebase.yml`, `capacity` is set to `CU_1` by default. Options: `CU_1`, `CU_2`, `CU_4`.

```yaml
resources:
  database_instances:
    memory:
      capacity: CU_2   # increase for higher concurrency
```

Then redeploy:
```bash
databricks bundle deploy -t staging
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Running without memory` in agent logs | `LAKEBASE_INSTANCE` not set in `app.yaml` | Add the env var and redeploy |
| `Connection refused` | Wrong host or instance stopped | Check `LAKEBASE_HOST` and instance state (step 1) |
| `authentication failed` | Credential token expired | Credentials are generated per-request; check `get_async_checkpointer()` is called fresh each invocation |
| `SSL connection required` | Missing `sslmode=require` | Verify the connection string includes `?sslmode=require` |
| `relation "checkpoints" does not exist` | `setup()` never ran | Call `checkpointer.setup()` once (step 7) |
| Agent starts fresh every call | Thread ID not passed through | Ensure `config = {"configurable": {"thread_id": ...}}` is passed to `graph.astream()` |
| Instance in `STOPPED` state | Idle instance auto-stopped | Restart via `databricks database-instances start --name <project>-memory` |
| High latency on first call | Cold credential generation | Pre-warm by calling `generate_database_credential` at App startup |

## How credentials work

Lakebase uses short-lived OAuth tokens (not static passwords). The `get_async_checkpointer()` function in `graph.py` calls `w.database.generate_database_credential()` on **every invocation** to ensure a fresh token. This is intentional — do not cache credentials.

```
agent.py (@invoke)
  └── get_async_checkpointer()        ← called per request
        └── generate_database_credential()  ← fresh token
              └── AsyncPostgresSaver(conn)
                    └── graph_builder.compile(checkpointer=checkpointer)
```
