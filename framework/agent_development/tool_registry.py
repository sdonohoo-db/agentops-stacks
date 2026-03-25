"""
Tool Registry
=============
Register Python functions as Unity Catalog AI tools available to agents
at inference time. UC-registered tools can be invoked by any LLM that
supports tool/function calling via the Databricks FM API.

UC AI Tools provide:
  - Governed access (UC permissions control who can invoke)
  - Discoverability (browsable in UC Explorer)
  - Versioning (functions are versioned SQL objects)
  - Multi-agent sharing (both Agent 1 and Agent 2 can share tools)

Registration pattern:
    1. Define a Python function
    2. Call register_tool() with the function and its schema
    3. The tool appears in UC and agents can call it via tool-calling

Reference:
    https://docs.databricks.com/en/generative-ai/agent-framework/create-custom-tool.html
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """
    Specification for a Unity Catalog AI tool.

    Args:
        name:        Short function name (no catalog/schema prefix).
        description: Human-readable description shown to LLMs and in UC Explorer.
        input_params: SQL parameter list, e.g. "query STRING, top_k INT DEFAULT 5"
        return_type:  SQL return type, e.g. "STRING" or "TABLE(id STRING, score DOUBLE)"
        body:         Python function body (string). Must return the declared type.
    """
    name: str
    description: str
    input_params: str
    return_type: str
    body: str
    tags: Dict[str, str] = field(default_factory=dict)


class ToolRegistry:
    """
    Manage Unity Catalog AI tool registration for an agent.

    Each agent creates a ToolRegistry instance and calls `register()`
    for each tool it needs. The registry handles creating/updating the
    UC functions idempotently.

    Example:
        >>> registry = ToolRegistry(agent_name="rag_agent")
        >>> registry.register(ToolSpec(
        ...     name="search_knowledge_base",
        ...     description="Search the knowledge base for relevant documents",
        ...     input_params="query STRING, top_k INT DEFAULT 5",
        ...     return_type="TABLE(chunk_id STRING, content STRING, score DOUBLE)",
        ...     body='''
        ...         # calls vector search
        ...         results = vector_search(query, top_k)
        ...         return results
        ...     ''',
        ... ))
        >>> tools = registry.get_tool_names()  # for passing to ChatDatabricks
    """

    def __init__(
        self,
        agent_name: str,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        self.config = config or get_config()
        self.agent_name = agent_name
        self.catalog = catalog or self.config.active_catalog
        self.schema = schema or self.config.active_schema
        self._registered: List[str] = []
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    def register(self, spec: ToolSpec) -> str:
        """
        Create or replace a Unity Catalog function from a ToolSpec.

        Args:
            spec: ToolSpec defining the function.

        Returns:
            Fully qualified function name (catalog.schema.name).

        Example:
            >>> fqn = registry.register(my_tool_spec)
            >>> print(fqn)
            agentops_dev.agentops.search_knowledge_base
        """
        fqn = f"{self.catalog}.{self.schema}.{spec.name}"
        comment = spec.description.replace("'", "\\'")

        sql = f"""
        CREATE OR REPLACE FUNCTION {fqn}({spec.input_params})
        RETURNS {spec.return_type}
        LANGUAGE PYTHON
        COMMENT '{comment}'
        AS $$
{spec.body}
        $$
        """

        try:
            self.spark.sql(sql)
            self._registered.append(fqn)
            logger.info("Registered UC tool: %s", fqn)
            return fqn
        except Exception as e:
            logger.error("Failed to register tool %s: %s", fqn, e)
            raise

    def register_many(self, specs: List[ToolSpec]) -> List[str]:
        """Register multiple tools at once. Returns list of FQNs."""
        return [self.register(spec) for spec in specs]

    def get_tool_names(self) -> List[str]:
        """
        Return all registered tool FQNs.

        Pass this list to the `tools` parameter of UCFunctionToolkit
        when constructing an agent chain.

        Example:
            >>> from databricks_langchain import UCFunctionToolkit
            >>> toolkit = UCFunctionToolkit(tools=registry.get_tool_names())
        """
        return list(self._registered)

    def list_existing(self) -> List[Dict[str, str]]:
        """
        List all UC functions in this registry's catalog/schema.

        Returns:
            List of dicts with "name", "full_name", "comment" keys.
        """
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient()
        functions = client.functions.list(
            catalog_name=self.catalog,
            schema_name=self.schema,
        )
        return [
            {"name": fn.name, "full_name": fn.full_name, "comment": fn.comment or ""}
            for fn in functions
        ]

    def drop(self, function_name: str) -> None:
        """
        Drop a UC function by short name.

        Args:
            function_name: Short name (no catalog/schema prefix).
        """
        fqn = f"{self.catalog}.{self.schema}.{function_name}"
        self.spark.sql(f"DROP FUNCTION IF EXISTS {fqn}")
        self._registered = [f for f in self._registered if f != fqn]
        logger.info("Dropped UC function: %s", fqn)


def tool_spec_from_function(func: Callable, return_type: str = "STRING") -> ToolSpec:
    """
    Auto-generate a ToolSpec from a Python function's signature and docstring.

    Args:
        func:        Python function to wrap.
        return_type: SQL return type string.

    Returns:
        ToolSpec ready for registration.

    Example:
        >>> def search_docs(query: str, top_k: int = 5) -> str:
        ...     '''Search indexed documents. Returns top_k relevant passages.'''
        ...     pass
        >>>
        >>> spec = tool_spec_from_function(search_docs, return_type="STRING")
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or func.__name__

    # Build SQL parameter list from function signature
    params = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        annotation = param.annotation
        # Map Python types to SQL types
        type_map = {str: "STRING", int: "INT", float: "DOUBLE", bool: "BOOLEAN"}
        sql_type = type_map.get(annotation, "STRING")

        if param.default is not inspect.Parameter.empty:
            default_val = repr(param.default) if isinstance(param.default, str) else param.default
            params.append(f"{param_name} {sql_type} DEFAULT {default_val}")
        else:
            params.append(f"{param_name} {sql_type}")

    # Extract function body
    source_lines = inspect.getsource(func).split("\n")
    # Skip the def line and docstring, keep the body
    body_lines = []
    in_body = False
    for line in source_lines:
        if in_body:
            body_lines.append(line)
        elif line.strip().startswith("def "):
            in_body = True

    body = "\n".join(body_lines).strip()

    return ToolSpec(
        name=func.__name__,
        description=doc,
        input_params=", ".join(params),
        return_type=return_type,
        body=body,
    )
