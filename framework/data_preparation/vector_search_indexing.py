"""
Vector Search Indexing
======================
Create and synchronize Databricks Vector Search indexes from the
document chunks Delta table.

Uses Delta Sync indexes (recommended) which automatically stay in sync
as the source Delta table is updated. The embedding model is managed
by Databricks, eliminating the need to generate embeddings separately.

Architecture:
    chunks Delta table → Vector Search Endpoint → Vector Search Index
                         (embedding happens inside VS)

The resulting index is queried by agents at inference time for
retrieval-augmented generation (RAG).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    """Result from a vector search indexing operation."""
    index_name: str
    status: str
    num_indexed_rows: int
    errors: List[str]

    @property
    def success(self) -> bool:
        return self.status == "ONLINE" and len(self.errors) == 0


class VectorSearchIndexer:
    """
    Create, update, and synchronize a Databricks Vector Search index
    backed by a Delta Sync source (the document chunks table).

    Best practices:
    - Use Delta Sync indexes (not Direct Vector Access) for production.
      Delta Sync automatically reindexes when source data changes.
    - One index per catalog/schema — multiple agents share it via filters.
    - Always wait for ONLINE status before running agents against the index.

    Example:
        >>> indexer = VectorSearchIndexer()
        >>> result = indexer.create_or_sync()
        >>> print(f"Index {result.index_name}: {result.status}")
    """

    def __init__(
        self,
        source_table: Optional[str] = None,
        index_name: Optional[str] = None,
        primary_key: str = "chunk_id",
        embedding_source_column: str = "content",
        embedding_model_endpoint: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        """
        Args:
            source_table:              Delta table to sync from.
                                       Defaults to config.chunks_table_name.
            index_name:                Fully qualified index name.
                                       Defaults to config.vector_search_index_name.
            primary_key:               Column to use as the unique document key.
            embedding_source_column:   Column to embed (must be STRING).
            embedding_model_endpoint:  Databricks embedding endpoint.
                                       Defaults to config.embedding_endpoint.
            config:                    AgentOpsConfig instance.
        """
        self.config = config or get_config()
        self.source_table = source_table or self.config.chunks_table_name
        self.index_name = index_name or self.config.vector_search_index_name
        self.primary_key = primary_key
        self.embedding_source_column = embedding_source_column
        self.embedding_model_endpoint = (
            embedding_model_endpoint or self.config.embedding_endpoint
        )

    def _get_client(self):
        from databricks.vector_search.client import VectorSearchClient
        return VectorSearchClient()

    def ensure_endpoint(self) -> None:
        """
        Create the Vector Search endpoint if it does not exist.
        This is idempotent — safe to call on every pipeline run.
        """
        client = self._get_client()
        endpoint_name = self.config.vector_search_endpoint

        try:
            client.get_endpoint(endpoint_name)
            logger.debug("Vector Search endpoint '%s' already exists.", endpoint_name)
        except Exception:
            logger.info("Creating Vector Search endpoint '%s'...", endpoint_name)
            client.create_endpoint(name=endpoint_name, endpoint_type="STANDARD")
            self._wait_for_endpoint(client, endpoint_name)

    def _wait_for_endpoint(
        self, client: Any, endpoint_name: str, timeout_seconds: int = 600
    ) -> None:
        elapsed = 0
        while elapsed < timeout_seconds:
            status = client.get_endpoint(endpoint_name).get("endpoint_status", {})
            state = status.get("state", "UNKNOWN")
            if state == "ONLINE":
                logger.info("Endpoint '%s' is ONLINE.", endpoint_name)
                return
            logger.debug("Endpoint state: %s (elapsed %ds)", state, elapsed)
            time.sleep(15)
            elapsed += 15
        raise TimeoutError(f"Endpoint '{endpoint_name}' did not reach ONLINE in {timeout_seconds}s")

    def create_or_sync(self, wait_for_online: bool = True) -> IndexingResult:
        """
        Create the Delta Sync index if it doesn't exist, then trigger a sync.

        If the index already exists, only triggers a sync (not a full recreate).

        Args:
            wait_for_online: Block until the index reaches ONLINE status.
                             Set False for fire-and-forget in CI pipelines.

        Returns:
            IndexingResult with current index status.

        Example:
            >>> result = VectorSearchIndexer().create_or_sync()
            >>> assert result.success
        """
        self.ensure_endpoint()
        client = self._get_client()
        endpoint_name = self.config.vector_search_endpoint

        try:
            index = client.get_index(
                endpoint_name=endpoint_name,
                index_name=self.index_name,
            )
            logger.info("Index '%s' exists — triggering sync.", self.index_name)
            index.sync()
        except Exception:
            logger.info("Creating index '%s'...", self.index_name)
            index = client.create_delta_sync_index(
                endpoint_name=endpoint_name,
                index_name=self.index_name,
                source_table_name=self.source_table,
                pipeline_type="TRIGGERED",
                primary_key=self.primary_key,
                embedding_source_column=self.embedding_source_column,
                embedding_model_endpoint_name=self.embedding_model_endpoint,
            )

        if wait_for_online:
            status = self._wait_for_index(client, endpoint_name)
        else:
            status = "PROVISIONING"

        indexed_rows = self._get_indexed_row_count(client, endpoint_name)
        return IndexingResult(
            index_name=self.index_name,
            status=status,
            num_indexed_rows=indexed_rows,
            errors=[],
        )

    def _wait_for_index(
        self, client: Any, endpoint_name: str, timeout_seconds: int = 1800
    ) -> str:
        elapsed = 0
        while elapsed < timeout_seconds:
            idx = client.get_index(endpoint_name=endpoint_name, index_name=self.index_name)
            status = idx.describe().get("status", {})
            state = status.get("detailed_state", "UNKNOWN")
            if state == "ONLINE":
                logger.info("Index '%s' is ONLINE.", self.index_name)
                return "ONLINE"
            if "FAILED" in state:
                logger.error("Index '%s' failed: %s", self.index_name, status)
                return state
            logger.debug("Index state: %s (elapsed %ds)", state, elapsed)
            time.sleep(30)
            elapsed += 30
        raise TimeoutError(f"Index '{self.index_name}' did not reach ONLINE in {timeout_seconds}s")

    def _get_indexed_row_count(self, client: Any, endpoint_name: str) -> int:
        try:
            idx = client.get_index(endpoint_name=endpoint_name, index_name=self.index_name)
            desc = idx.describe()
            return desc.get("status", {}).get("indexed_row_count", 0)
        except Exception:
            return 0

    def get_retriever(
        self,
        num_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """
        Return a LangChain-compatible retriever for this index.

        Used by agents during development and inference.

        Args:
            num_results: Number of chunks to retrieve per query.
            filters:     Optional metadata filters (e.g., {"doc_type": "policy"}).

        Returns:
            DatabricksVectorSearch retriever object.

        Example:
            >>> retriever = indexer.get_retriever(num_results=5)
            >>> docs = retriever.invoke("What is the refund policy?")
        """
        from langchain_databricks.vectorstores import DatabricksVectorSearch

        vs = DatabricksVectorSearch(
            endpoint=self.config.vector_search_endpoint,
            index_name=self.index_name,
            text_column=self.embedding_source_column,
        )
        return vs.as_retriever(
            search_kwargs={
                "k": num_results,
                **({"filters": filters} if filters else {}),
            }
        )
