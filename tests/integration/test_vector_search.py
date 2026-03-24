"""
Integration Tests: Vector Search
Tests Databricks Vector Search index availability and query correctness.
Requires: DATABRICKS_HOST and DATABRICKS_TOKEN env vars.

These tests verify the Dev Catalog Vector Search index is queryable
and returns semantically relevant results for representative queries.
"""

import os

import pytest

from framework.config import get_config

# Skip if not in a Databricks environment
requires_databricks = pytest.mark.skipif(
    not os.environ.get("DATABRICKS_HOST"),
    reason="Requires DATABRICKS_HOST env var (Databricks environment)",
)


@requires_databricks
class TestVectorSearchIndex:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = get_config()
        self.index_name = self.config.vector_search_index_name

    def _get_vs_client(self):
        from databricks.vector_search.client import VectorSearchClient
        return VectorSearchClient()

    def test_index_exists(self):
        """Index should exist and be queryable."""
        client = self._get_vs_client()
        index = client.get_index(self.index_name)
        assert index is not None

    def test_index_is_ready(self):
        """Index should be in ONLINE state."""
        client = self._get_vs_client()
        index = client.get_index(self.index_name)
        status = index.describe()
        state = status.get("status", {}).get("detailed_state", "UNKNOWN")
        assert state in ("ONLINE", "ONLINE_NO_PENDING_UPDATE"), (
            f"Vector Search index not ready. State: {state}"
        )

    def test_similarity_search_returns_results(self):
        """A representative query should return at least one result."""
        client = self._get_vs_client()
        index = client.get_index(self.index_name)

        results = index.similarity_search(
            query_text="What is the refund policy?",
            columns=["chunk_id", "content", "source"],
            num_results=3,
        )

        data = results.get_dict().get("result", {}).get("data_array", [])
        assert len(data) > 0, "No results returned from Vector Search"

    def test_similarity_search_content_field_present(self):
        """Results should include the 'content' field."""
        client = self._get_vs_client()
        index = client.get_index(self.index_name)

        results = index.similarity_search(
            query_text="vacation policy",
            columns=["chunk_id", "content"],
            num_results=1,
        )

        data = results.get_dict().get("result", {}).get("data_array", [])
        assert len(data) > 0
        # data_array is a list of lists; columns order matches requested columns
        # Each row: [chunk_id, content]
        row = data[0]
        assert len(row) == 2
        assert isinstance(row[1], str) and len(row[1]) > 0

    def test_langchain_retriever_compatible(self):
        """DatabricksVectorSearch should work as a LangChain retriever."""
        from langchain_databricks import DatabricksVectorSearch

        retriever = DatabricksVectorSearch(
            endpoint=self.config.vector_search_endpoint,
            index_name=self.index_name,
            columns=["content", "source"],
        ).as_retriever(search_kwargs={"k": 3})

        docs = retriever.invoke("employee benefits")
        assert len(docs) > 0
        assert hasattr(docs[0], "page_content")
        assert len(docs[0].page_content) > 0

    def test_search_returns_relevant_content(self):
        """Results for 'sick leave' should contain policy-related text."""
        client = self._get_vs_client()
        index = client.get_index(self.index_name)

        results = index.similarity_search(
            query_text="how many sick days do employees get",
            columns=["content"],
            num_results=3,
        )

        data = results.get_dict().get("result", {}).get("data_array", [])
        all_content = " ".join(row[0].lower() for row in data)

        # At least one result should mention sick leave or days
        assert any(keyword in all_content for keyword in ["sick", "leave", "day"]), (
            f"Results don't seem relevant to sick leave query. Got: {all_content[:200]}"
        )
