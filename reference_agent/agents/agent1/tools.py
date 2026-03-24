"""
RAG Agent Tools
===============
Unity Catalog tools for the RAG agent (Agent 1).

These functions are registered in Unity Catalog and invoked by the agent
via tool-calling. They provide structured access to the knowledge base
and supporting data.

Registration:
    Run this file to register all tools:
    $ python reference_agent/agents/agent1/tools.py

Or trigger the agent1_tools task in the agent_development_workflow DAB job.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from framework.agent_development.tool_registry import ToolRegistry, ToolSpec
from framework.config import get_config

logger = logging.getLogger(__name__)


def get_agent1_tool_registry(
    config: Optional[Any] = None,
    spark: Optional[Any] = None,
) -> ToolRegistry:
    """
    Create and return the ToolRegistry for Agent 1 (RAG Agent).

    Returns:
        ToolRegistry with all Agent 1 tools registered.

    Example:
        >>> registry = get_agent1_tool_registry()
        >>> print(registry.get_tool_names())
    """
    cfg = config or get_config()
    registry = ToolRegistry(
        agent_name="rag_agent",
        config=cfg,
        spark=spark,
    )
    return registry


def register_agent1_tools(
    config: Optional[Any] = None,
    spark: Optional[Any] = None,
) -> ToolRegistry:
    """
    Register all Agent 1 tools in Unity Catalog.

    Called by the agent1_tools task in the agent_development_workflow.

    Returns:
        ToolRegistry with registered tool FQNs.
    """
    cfg = config or get_config()
    registry = get_agent1_tool_registry(config=cfg, spark=spark)

    # Tool 1: Vector search lookup
    registry.register(ToolSpec(
        name="search_knowledge_base",
        description=(
            "Search the knowledge base for documents relevant to a query. "
            "Returns the top-k most relevant document chunks with their content "
            "and source metadata. Use this to retrieve context before answering questions."
        ),
        input_params="query STRING, top_k INT DEFAULT 5",
        return_type="TABLE(chunk_id STRING, content STRING, doc_id STRING, score DOUBLE)",
        body=f"""
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()
index = vsc.get_index(
    endpoint_name="{cfg.vector_search_endpoint}",
    index_name="{cfg.vector_search_index_name}",
)
results = index.similarity_search(
    query_text=query,
    columns=["chunk_id", "content", "doc_id"],
    num_results=top_k,
)
col_names = [c["name"] for c in results.get("manifest", {{}}).get("columns", [])]
rows = results.get("result", {{}}).get("data_array", [])
return [dict(zip(col_names, row)) for row in rows]
""",
        tags={"agent": "rag_agent", "type": "retrieval"},
    ))

    # Tool 2: Document metadata lookup
    registry.register(ToolSpec(
        name="get_document_metadata",
        description=(
            "Retrieve metadata for a specific document by its ID. "
            "Returns title, source URL, document type, and other metadata. "
            "Use this when you need details about where a chunk came from."
        ),
        input_params="doc_id STRING",
        return_type="TABLE(doc_id STRING, title STRING, source STRING, document_type STRING)",
        body=f"""
from pyspark.sql import SparkSession
spark = SparkSession.getActiveSession()
df = spark.table("{cfg.active_catalog_schema}.raw_documents").filter(f"id = '{{doc_id}}'")
rows = df.select("id", "metadata").collect()
results = []
for row in rows:
    meta = row.metadata or {{}}
    results.append({{
        "doc_id": row.id,
        "title": meta.get("title", ""),
        "source": meta.get("source_url", meta.get("source_path", "")),
        "document_type": meta.get("document_type", "unknown"),
    }})
return results
""",
        tags={"agent": "rag_agent", "type": "metadata"},
    ))

    # Tool 3: Related chunks finder
    registry.register(ToolSpec(
        name="get_related_chunks",
        description=(
            "Find chunks from the same document as a given chunk. "
            "Useful for expanding context when a chunk references other sections "
            "of the same document."
        ),
        input_params="chunk_id STRING, num_chunks INT DEFAULT 3",
        return_type="TABLE(chunk_id STRING, content STRING, chunk_index INT)",
        body=f"""
from pyspark.sql import SparkSession
import re
spark = SparkSession.getActiveSession()
# Extract doc_id from chunk_id (format: doc_id_chunkindex)
doc_id = "_".join(chunk_id.split("_")[:-1])
df = spark.table("{cfg.chunks_table_name}").filter(f"doc_id = '{{doc_id}}'").orderBy("chunk_index").limit(num_chunks)
return df.select("chunk_id", "content", "chunk_index").collect()
""",
        tags={"agent": "rag_agent", "type": "retrieval"},
    ))

    logger.info("Registered %d Agent 1 tools", len(registry.get_tool_names()))
    return registry


if __name__ == "__main__":
    import os
    os.environ.setdefault("AGENTOPS_ENV", "dev")
    registry = register_agent1_tools()
    print("Registered tools:")
    for tool in registry.get_tool_names():
        print(f"  {tool}")
