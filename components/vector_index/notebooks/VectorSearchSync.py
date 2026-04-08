# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Vector Search Index Sync
# MAGIC Creates or updates a Delta Sync Vector Search index from a UC source table.

# COMMAND ----------
dbutils.widgets.text("vs_endpoint_name", "", "Vector Search Endpoint")
dbutils.widgets.text("vs_index_name", "", "Index Name (catalog.schema.index)")
dbutils.widgets.text("vs_source_table", "", "Source Table (catalog.schema.table)")
dbutils.widgets.text("vs_embedding_endpoint", "databricks-bge-large-en", "Embedding Endpoint")
dbutils.widgets.text("vs_text_column", "content", "Text Column")
dbutils.widgets.text("vs_id_column", "id", "ID Column")

# COMMAND ----------
vs_endpoint_name = dbutils.widgets.get("vs_endpoint_name")
vs_index_name = dbutils.widgets.get("vs_index_name")
vs_source_table = dbutils.widgets.get("vs_source_table")
vs_embedding_endpoint = dbutils.widgets.get("vs_embedding_endpoint")
vs_text_column = dbutils.widgets.get("vs_text_column")
vs_id_column = dbutils.widgets.get("vs_id_column")

print(f"Endpoint:  {vs_endpoint_name}")
print(f"Index:     {vs_index_name}")
print(f"Source:    {vs_source_table}")
print(f"Embedding: {vs_embedding_endpoint}")

# COMMAND ----------
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create or get endpoint

# COMMAND ----------
existing_endpoints = [ep["name"] for ep in vsc.list_endpoints().get("endpoints", [])]

if vs_endpoint_name not in existing_endpoints:
    print(f"Creating endpoint: {vs_endpoint_name}")
    vsc.create_endpoint(name=vs_endpoint_name, endpoint_type="STANDARD")
else:
    print(f"Endpoint exists: {vs_endpoint_name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create or sync index

# COMMAND ----------
import time


def get_index_status(vsc, index_name):
    try:
        idx = vsc.get_index(index_name=index_name)
        return idx.describe()
    except Exception:
        return None


status = get_index_status(vsc, vs_index_name)

if status is None:
    print(f"Creating Delta Sync index: {vs_index_name}")
    vsc.create_delta_sync_index(
        endpoint_name=vs_endpoint_name,
        index_name=vs_index_name,
        source_table_name=vs_source_table,
        primary_key=vs_id_column,
        pipeline_type="TRIGGERED",
        embedding_source_column=vs_text_column,
        embedding_model_endpoint_name=vs_embedding_endpoint,
    )
    print("Index creation initiated.")
else:
    print(f"Index exists. Current status: {status.get('status', {}).get('ready', 'UNKNOWN')}")
    idx = vsc.get_index(index_name=vs_index_name)
    idx.sync()
    print("Sync triggered.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Wait for index ready

# COMMAND ----------
for i in range(60):
    status = get_index_status(vsc, vs_index_name)
    ready = status.get("status", {}).get("ready", False) if status else False
    if ready:
        print(f"Index is ready. Rows: {status.get('status', {}).get('num_rows', 'unknown')}")
        break
    print(f"Waiting for index... ({i * 30}s)")
    time.sleep(30)
else:
    print("WARNING: Index not ready after 30 minutes. Check status manually.")

# COMMAND ----------
dbutils.notebook.exit("SUCCESS")
