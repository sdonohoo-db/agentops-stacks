# vector_index

Vector Search index component with sync pipeline from a Unity Catalog source table.

## What it provides

- Vector Search endpoint resource (or reference to existing endpoint)
- Delta Sync index definition pointing at a UC source table
- Notebook for index creation, sync management, and status monitoring
- Optional scheduled job for periodic re-sync

## Dependencies

- Unity Catalog table with text content to index (source table)
- An embedding model endpoint (Foundation Model API or custom serving endpoint)
- `agent_app_base` component is not required but typically used together for RAG patterns

## Files

- `databricks.yml` — Vector Search endpoint and index resource definitions, variables
- `notebooks/VectorSearchSync.py` — creates/updates the index, monitors sync status
- `jobs/vector-sync-job.yml` — optional scheduled job for periodic re-sync

## Integration

1. Copy `databricks.yml` contents into your project's `resources/` directory
2. Copy `notebooks/` to your project's notebook directory
3. Add required variables to your root `databricks.yml`
4. Set the source table, embedding endpoint, and index name variables per target
5. Optionally include `jobs/vector-sync-job.yml` if you need scheduled re-indexing

## Variables

| Variable | Description | Default |
|---|---|---|
| `vs_endpoint_name` | Vector Search endpoint name | `${bundle.target}-${bundle.name}-vs-endpoint` |
| `vs_index_name` | Fully qualified index name | — (required) |
| `vs_source_table` | UC table to index (catalog.schema.table) | — (required) |
| `vs_embedding_endpoint` | Embedding model serving endpoint | `databricks-bge-large-en` |
| `vs_text_column` | Column containing text to embed | `content` |
| `vs_id_column` | Primary key column | `id` |

## Composing with agent_app_base

To add retrieval to an agent app, add this component's variables and resources, then reference the index in your agent code:

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()
index = vsc.get_index(index_name=os.environ["VS_INDEX_NAME"])
results = index.similarity_search(query_text=query, columns=["content"], num_results=3)
```

Add `VS_INDEX_NAME` to your app's env vars in the agent_app_base `databricks.yml`:
```yaml
env:
  - name: VS_INDEX_NAME
    value: ${var.vs_index_name}
```
