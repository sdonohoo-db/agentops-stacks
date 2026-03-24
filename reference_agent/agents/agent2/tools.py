"""
Summarization Agent Tools
=========================
Unity Catalog tools for the Summarization Agent (Agent 2).

Agent 2 has minimal tools compared to Agent 1 — its core capability
is text summarization via the LLM, not retrieval. These tools provide
supporting functionality for summarization workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from framework.agent_development.tool_registry import ToolRegistry, ToolSpec
from framework.config import get_config

logger = logging.getLogger(__name__)


def register_agent2_tools(
    config: Optional[Any] = None,
    spark: Optional[Any] = None,
) -> ToolRegistry:
    """
    Register Agent 2 tools in Unity Catalog.

    Returns:
        ToolRegistry with registered tool FQNs.
    """
    cfg = config or get_config()
    registry = ToolRegistry(
        agent_name="summarization_agent",
        config=cfg,
        spark=spark,
    )

    # Tool 1: Fetch document by ID for summarization
    registry.register(ToolSpec(
        name="get_document_for_summary",
        description=(
            "Retrieve the full text of a document by its ID for summarization. "
            "Returns the complete document content from the knowledge base."
        ),
        input_params="doc_id STRING",
        return_type="TABLE(doc_id STRING, content STRING, title STRING)",
        body=f"""
from pyspark.sql import SparkSession
spark = SparkSession.getActiveSession()
df = spark.table("{cfg.active_catalog_schema}.raw_documents").filter(f"id = '{{doc_id}}'")
rows = df.collect()
return [{{"doc_id": r.id, "content": r.content, "title": r.metadata.get("title", "")}} for r in rows]
""",
        tags={"agent": "summarization_agent", "type": "retrieval"},
    ))

    # Tool 2: Count words (useful for length-constrained summaries)
    registry.register(ToolSpec(
        name="count_words",
        description="Count the number of words in a text string.",
        input_params="text STRING",
        return_type="INT",
        body="return len(text.split()) if text else 0",
        tags={"agent": "summarization_agent", "type": "utility"},
    ))

    logger.info("Registered %d Agent 2 tools", len(registry.get_tool_names()))
    return registry


if __name__ == "__main__":
    import os
    os.environ.setdefault("AGENTOPS_ENV", "dev")
    registry = register_agent2_tools()
    print("Registered tools:")
    for tool in registry.get_tool_names():
        print(f"  {tool}")
