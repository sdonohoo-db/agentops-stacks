"""
Integration Tests: Unity Catalog Tool Invocation
Tests that UC-registered tools are callable from the dev catalog.
Requires: DATABRICKS_HOST, DATABRICKS_TOKEN, and a Spark session.

These tests verify that tools registered by agent1 and agent2 exist
in Unity Catalog and return expected output shapes when invoked.
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
class TestUCToolRegistry:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = get_config()
        self.catalog = self.config.active_catalog
        self.schema = self.config.active_schema

    def _get_workspace_client(self):
        from databricks.sdk import WorkspaceClient
        return WorkspaceClient()

    def _get_function_fqn(self, func_name: str) -> str:
        return f"{self.catalog}.{self.schema}.{func_name}"

    def test_rag_agent_tools_registered(self):
        """Tools registered by agent1 (RAG agent) should exist in UC."""
        client = self._get_workspace_client()
        expected_tools = ["search_knowledge_base", "get_document_metadata", "get_related_chunks"]

        registered = {
            f.name
            for f in client.functions.list(
                catalog_name=self.catalog,
                schema_name=self.schema,
            )
        }

        for tool in expected_tools:
            assert tool in registered, (
                f"Tool '{tool}' not found in {self.catalog}.{self.schema}. "
                f"Available: {sorted(registered)}"
            )

    def test_summarization_agent_tools_registered(self):
        """Tools registered by agent2 (summarization) should exist in UC."""
        client = self._get_workspace_client()
        expected_tools = ["get_document_for_summary", "count_words"]

        registered = {
            f.name
            for f in client.functions.list(
                catalog_name=self.catalog,
                schema_name=self.schema,
            )
        }

        for tool in expected_tools:
            assert tool in registered, (
                f"Tool '{tool}' not found in {self.catalog}.{self.schema}"
            )

    def test_tool_has_expected_schema(self):
        """UC function schema should match the registered spec."""
        client = self._get_workspace_client()
        fqn = self._get_function_fqn("get_document_metadata")

        func = client.functions.get(fqn)
        assert func is not None
        assert func.full_name == fqn

        # Should have at least one input parameter
        params = func.input_params.parameters if func.input_params else []
        assert len(params) >= 1, f"Expected parameters for {fqn}, got none"

    def test_tool_invocable_via_spark_sql(self):
        """UC function should be callable via spark.sql()."""
        pytest.importorskip("pyspark")
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession()
        if spark is None:
            pytest.skip("No active Spark session available")

        fqn = self._get_function_fqn("get_document_metadata")

        # Call the function with a test document ID
        result_df = spark.sql(f"SELECT {fqn}('test-doc-001') AS result")
        result = result_df.collect()

        assert len(result) == 1
        # Function should return a non-null result (even if doc not found, returns a dict)
        assert result[0]["result"] is not None


@requires_databricks
class TestToolRegistryHelpers:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = get_config()

    def test_tool_registry_lists_tools(self):
        """ToolRegistry.get_tool_names() should return the registered tools."""
        from framework.agent_development.tool_registry import ToolRegistry

        registry = ToolRegistry(
            agent_name="test_registry_listing",
            config=self.config,
        )
        # A fresh registry has no tools
        names = registry.get_tool_names()
        assert isinstance(names, list)

    def test_tool_registry_validates_spec(self):
        """ToolRegistry should reject specs missing required fields."""
        from framework.agent_development.tool_registry import ToolRegistry, ToolSpec

        registry = ToolRegistry(agent_name="test_validation", config=self.config)

        with pytest.raises((ValueError, TypeError)):
            registry.register(ToolSpec(
                name="",  # empty name should fail
                description="test",
                input_params="x STRING",
                return_type="STRING",
                body="return x",
            ))
