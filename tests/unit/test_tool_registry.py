"""
Unit Tests: Tool Registry
Tests ToolSpec construction and tool_spec_from_function without Databricks.
"""

import pytest

from framework.agent_development.tool_registry import ToolSpec, tool_spec_from_function


class TestToolSpec:
    def test_basic_construction(self):
        spec = ToolSpec(
            name="my_tool",
            description="A test tool",
            input_params="query STRING",
            return_type="STRING",
            body="return query.upper()",
        )
        assert spec.name == "my_tool"
        assert spec.description == "A test tool"
        assert spec.input_params == "query STRING"
        assert spec.return_type == "STRING"

    def test_default_tags_empty(self):
        spec = ToolSpec(
            name="my_tool",
            description="desc",
            input_params="",
            return_type="STRING",
            body="return ''",
        )
        assert spec.tags == {}

    def test_tags_set_correctly(self):
        spec = ToolSpec(
            name="my_tool",
            description="desc",
            input_params="",
            return_type="STRING",
            body="return ''",
            tags={"agent": "rag_agent"},
        )
        assert spec.tags["agent"] == "rag_agent"


class TestToolSpecFromFunction:
    def test_string_param_detection(self):
        def my_func(query: str) -> str:
            """A search function."""
            return query

        spec = tool_spec_from_function(my_func, return_type="STRING")
        assert "query" in spec.input_params
        assert "STRING" in spec.input_params

    def test_int_param_detection(self):
        def my_func(n: int) -> str:
            """An int param function."""
            return str(n)

        spec = tool_spec_from_function(my_func, return_type="STRING")
        assert "INT" in spec.input_params

    def test_default_param_included(self):
        def my_func(query: str, top_k: int = 5) -> str:
            """Function with default."""
            return query

        spec = tool_spec_from_function(my_func, return_type="STRING")
        assert "DEFAULT" in spec.input_params
        assert "5" in spec.input_params

    def test_description_from_docstring(self):
        def my_func(x: str) -> str:
            """This is the docstring description."""
            return x

        spec = tool_spec_from_function(my_func)
        assert "docstring description" in spec.description

    def test_name_from_function(self):
        def search_knowledge_base(query: str) -> str:
            """Search."""
            return query

        spec = tool_spec_from_function(search_knowledge_base)
        assert spec.name == "search_knowledge_base"
