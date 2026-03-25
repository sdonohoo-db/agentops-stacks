---
title: Data Preparation
description: Ingest, chunk, and index documents for RAG agents using Databricks Vector Search and unstructured document parsing
category: data
tags: [data-preparation, vector-search, chunking, ingestion, unstructured, rag]
related_docs: [agent-development.md, architecture.md]
---

# Data Preparation

The data preparation pipeline transforms raw documents into a Vector Search index that RAG agents query at inference time. It runs as a DAB workflow with two parallel paths: **structured** (PDFs, HTML, plain text) and **unstructured** (complex PDFs requiring AI-assisted extraction).

---

## Pipeline Overview

```
Structured path:
  ingestion.py → chunking.py → vector_search_indexing.py

Unstructured path:
  ai_parse_document() → ai_query_extraction() → data_preparation.py
```

Both paths write normalized `ChunkedDocument` records to a Delta table in the dev catalog, which is then synced into a Vector Search index.

---

## Workflow: `data_preparation_workflow`

Defined in `bundle/resources/data_preparation_workflow.yml`. Six tasks:

| Task | Module | Depends On |
|---|---|---|
| `ingest_structured` | `framework.data_preparation.ingestion` | — |
| `chunk_structured` | `framework.data_preparation.chunking` | `ingest_structured` |
| `index_structured` | `framework.data_preparation.vector_search_indexing` | `chunk_structured` |
| `parse_unstructured` | `framework.data_preparation.unstructured.ai_parse_document` | — |
| `extract_unstructured` | `framework.data_preparation.unstructured.ai_query_extraction` | `parse_unstructured` |
| `normalize_unstructured` | `framework.data_preparation.unstructured.data_preparation` | `extract_unstructured` |

---

## Ingestion

### `DataIngestionBase`

```python
from framework.data_preparation.ingestion import DataIngestionBase

class MyIngestion(DataIngestionBase):
    def ingest(self) -> List[RawDocument]:
        # Return list of RawDocument(source, content, metadata)
        ...
```

### `DeltaTableIngestion`

Built-in ingester that reads from a Delta table. The dev catalog has **read-only access** to the prod catalog — always read source data from prod.

```python
from framework.data_preparation.ingestion import DeltaTableIngestion

ingester = DeltaTableIngestion(
    table_name="agentops_prod.raw.policy_documents",
    text_column="content",
    metadata_columns=["title", "category", "updated_at"],
    spark=spark,
)
documents = ingester.ingest()
```

---

## Chunking

### `RecursiveCharacterChunker`

Standard chunker for most text documents. Splits on paragraph → sentence → word boundaries.

```python
from framework.data_preparation.chunking import RecursiveCharacterChunker

chunker = RecursiveCharacterChunker(chunk_size=512, chunk_overlap=64)

# Direct use (unit-testable, no Spark):
text_chunks = chunker.chunk_text("Long document text...")  # Returns List[str]

# Spark batch use (DAB workflow):
result = chunker.run()  # Reads source_table, writes target_table
print(f"Produced {result.chunks_produced} chunks in {result.target_table}")
```

### `SemanticChunker`

Groups sentences by approximate word count, respecting sentence boundaries. Better for technical prose with natural topic flow.

```python
from framework.data_preparation.chunking import SemanticChunker

chunker = SemanticChunker(target_chunk_words=200, max_chunk_words=300)

# Direct use:
text_chunks = chunker.chunk_text(document_text)  # Returns List[str]

# Spark batch use:
result = chunker.run()
```

### Chunk output schema (Delta table)

| Column | Type | Description |
|---|---|---|
| `chunk_id` | STRING | `{doc_id}_{chunk_index}` — globally unique |
| `doc_id` | STRING | Parent document ID from ingestion |
| `content` | STRING | Chunk text content |
| `chunk_index` | INT | Position of this chunk within the source document |
| `metadata` | MAP\<STRING,STRING\> | Inherited from the parent document |

---

## Vector Search Indexing

After chunking, `vector_search_indexing.py` creates or syncs a **Delta Sync** index in Databricks Vector Search.

```python
from framework.data_preparation.vector_search_indexing import VectorSearchIndexer

indexer = VectorSearchIndexer(
    endpoint_name="agentops_vs_endpoint",
    index_name="agentops_dev.agentops.agentops_vs_index",
    source_table="agentops_dev.agentops.document_chunks",
    embedding_column="content",
    embedding_model_endpoint="databricks-gte-large-en",
)
indexer.create_or_sync()
```

The index is created as a **Delta Sync index** — it stays in sync with the source Delta table automatically on a schedule or on-demand trigger.

### Querying the index (from an agent)

```python
from langchain_databricks import DatabricksVectorSearch

retriever = DatabricksVectorSearch(
    endpoint="agentops_vs_endpoint",
    index_name="agentops_dev.agentops.agentops_vs_index",
    columns=["chunk_id", "content", "source", "metadata"],
).as_retriever(search_kwargs={"k": 5})

docs = retriever.invoke("What is the refund policy?")
```

---

## Unstructured Document Processing

For complex PDFs with tables, figures, or mixed layouts, use the AI-assisted unstructured path.

### `ai_parse_document()`

Wraps the Databricks `ai_parse_document` SQL function to extract structured content from complex documents.

```python
from framework.data_preparation.unstructured.ai_parse_document import parse_documents

parsed_df = parse_documents(
    spark=spark,
    input_table="agentops_dev.agentops.raw_pdfs",
    output_table="agentops_dev.agentops.parsed_pdfs",
    file_column="file_path",
)
```

### `ai_query_extraction()`

Extracts structured fields from parsed text using an LLM query.

```python
from framework.data_preparation.unstructured.ai_query_extraction import extract_fields

extracted_df = extract_fields(
    spark=spark,
    input_table="agentops_dev.agentops.parsed_pdfs",
    output_table="agentops_dev.agentops.extracted_fields",
    extraction_prompt="Extract: title, effective_date, policy_number, summary",
)
```

---

## Triggering the Pipeline

### Via DAB workflow (recommended)

```bash
databricks jobs run-now --job-id <data_preparation_job_id>
```

Or trigger from the deploy script after bundle deployment.

### Locally (dev iteration)

```bash
# Structured path only
python -c "
from framework.data_preparation.ingestion import DeltaTableIngestion
from framework.data_preparation.chunking import RecursiveCharacterChunker
from framework.data_preparation.vector_search_indexing import VectorSearchIndexer
# ... wire together
"
```

---

## Dev Catalog vs Prod Catalog

| Operation | Catalog | Why |
|---|---|---|
| Read source documents | `agentops_prod` | Governed source of truth |
| Write chunks | `agentops_dev` | Isolated dev workspace |
| Vector Search index | `agentops_dev` | Dev agents query dev index |
| Promotion to staging | `agentops_staging` | CI re-runs pipeline on staging catalog |

The dev catalog has **read-only** grants on prod catalog tables. This is enforced at the Unity Catalog level — dev code cannot accidentally write to prod.

---

## Adding a New Data Source

1. Create a new ingester extending `DataIngestionBase`
2. Add it as a task in `bundle/resources/data_preparation_workflow.yml`
3. Register the output table as a new Vector Search index (or extend an existing one)
4. Update `reference_agent/agents/agent1/agent.py` to query the new index

See [Extension Guide](extension-guide.md) for the full walkthrough.
