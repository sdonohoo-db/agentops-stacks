"""
Unity Catalog Utilities
=======================
Helpers for ensuring catalog/schema existence, granting permissions,
and registering Python functions as Unity Catalog AI tools.

Design principles:
- Idempotent: all operations are safe to re-run
- Environment-aware: uses AgentOpsConfig for catalog/schema names
- Permission model: dev workspace gets read/write on dev catalog,
  read-only on prod catalog (enforced at UC level, not here)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


def ensure_catalog_schema(
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    config: Optional[AgentOpsConfig] = None,
    spark: Optional[Any] = None,
) -> None:
    """
    Idempotently create a Unity Catalog catalog and schema if they don't exist.

    Args:
        catalog: Catalog name. Defaults to config.active_catalog.
        schema:  Schema name.  Defaults to config.active_schema.
        config:  AgentOpsConfig. Defaults to get_config().
        spark:   SparkSession. If None, imports the active session.

    Example:
        >>> ensure_catalog_schema()  # uses ambient config
    """
    cfg = config or get_config()
    cat = catalog or cfg.active_catalog
    sch = schema or cfg.active_schema

    if spark is None:
        from pyspark.sql import SparkSession
        spark = SparkSession.getActiveSession()

    spark.sql(f"CREATE CATALOG IF NOT EXISTS {cat}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cat}.{sch}")
    logger.info("Ensured catalog/schema: %s.%s", cat, sch)


def grant_catalog_permissions(
    principal: str,
    catalog: Optional[str] = None,
    privileges: Optional[List[str]] = None,
    config: Optional[AgentOpsConfig] = None,
    spark: Optional[Any] = None,
) -> None:
    """
    Grant Unity Catalog privileges to a principal on a catalog.

    Args:
        principal: UC principal (user email, group name, or service principal).
        catalog:   Catalog name. Defaults to config.active_catalog.
        privileges: List of UC privilege strings. Defaults to
                    ["USE_CATALOG", "USE_SCHEMA", "SELECT"].
        config:    AgentOpsConfig. Defaults to get_config().
        spark:     SparkSession. If None, imports the active session.

    Example:
        >>> grant_catalog_permissions("data-science-group@company.com")
    """
    cfg = config or get_config()
    cat = catalog or cfg.active_catalog
    privs = privileges or ["USE_CATALOG", "USE_SCHEMA", "SELECT"]
    priv_str = ", ".join(privs)

    if spark is None:
        from pyspark.sql import SparkSession
        spark = SparkSession.getActiveSession()

    spark.sql(f"GRANT {priv_str} ON CATALOG {cat} TO `{principal}`")
    logger.info("Granted [%s] on catalog %s to %s", priv_str, cat, principal)


def register_uc_function(
    function_name: str,
    input_params: str,
    return_type: str,
    body: str,
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    comment: str = "",
    config: Optional[AgentOpsConfig] = None,
    spark: Optional[Any] = None,
) -> str:
    """
    Register a Python lambda as a Unity Catalog function (AI tool).

    Creates a SQL function using `CREATE OR REPLACE FUNCTION` with a
    Python handler body. The function is immediately available for
    tool-calling agents via the UC function invocation API.

    Args:
        function_name: Short name (no catalog/schema prefix).
        input_params:  SQL parameter list, e.g. "query STRING, top_k INT".
        return_type:   SQL return type, e.g. "STRING" or "TABLE(...)".
        body:          Python function body as a string. Must be valid Python
                       that returns the declared type.
        catalog:       Target catalog. Defaults to config.active_catalog.
        schema:        Target schema. Defaults to config.active_schema.
        comment:       Human-readable description shown in UC explorer.
        config:        AgentOpsConfig. Defaults to get_config().
        spark:         SparkSession.

    Returns:
        Fully qualified function name: "catalog.schema.function_name".

    Example:
        >>> fqn = register_uc_function(
        ...     function_name="get_document_count",
        ...     input_params="",
        ...     return_type="INT",
        ...     body="return 42",
        ...     comment="Returns the total number of indexed documents.",
        ... )
        >>> print(fqn)
        agentops_dev.agentops.get_document_count
    """
    cfg = config or get_config()
    cat = catalog or cfg.active_catalog
    sch = schema or cfg.active_schema
    fqn = f"{cat}.{sch}.{function_name}"

    if spark is None:
        from pyspark.sql import SparkSession
        spark = SparkSession.getActiveSession()

    comment_clause = f"COMMENT '{comment}'" if comment else ""
    sql = f"""
    CREATE OR REPLACE FUNCTION {fqn}({input_params})
    RETURNS {return_type}
    LANGUAGE PYTHON
    {comment_clause}
    AS $$
{body}
    $$
    """
    spark.sql(sql)
    logger.info("Registered UC function: %s", fqn)
    return fqn


def list_uc_functions(
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    config: Optional[AgentOpsConfig] = None,
) -> List[Dict[str, str]]:
    """
    List all Unity Catalog functions in the active catalog/schema.

    Returns:
        List of dicts with keys: "name", "full_name", "comment".

    Example:
        >>> functions = list_uc_functions()
        >>> for fn in functions:
        ...     print(fn["full_name"])
    """
    from databricks.sdk import WorkspaceClient

    cfg = config or get_config()
    cat = catalog or cfg.active_catalog
    sch = schema or cfg.active_schema

    client = WorkspaceClient()
    functions = client.functions.list(catalog_name=cat, schema_name=sch)

    return [
        {
            "name": fn.name,
            "full_name": fn.full_name,
            "comment": fn.comment or "",
        }
        for fn in functions
    ]
