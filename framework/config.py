"""
AgentOps Configuration
======================
Central configuration object for the AgentOps framework. Reads from
environment variables (set by Databricks Asset Bundle variable injection
or manually for local development).

Environment Variables
---------------------
AGENTOPS_ENV                    : "dev" | "staging" | "prod"  (default: "dev")
AGENTOPS_WORKSPACE_HOST         : Databricks workspace URL
AGENTOPS_DEV_CATALOG            : Unity Catalog name for dev assets  (default: "agentops_dev")
AGENTOPS_PROD_CATALOG           : Unity Catalog name for prod assets (default: "agentops_prod")
AGENTOPS_DEV_SCHEMA             : Schema within dev catalog           (default: "agentops")
AGENTOPS_PROD_SCHEMA            : Schema within prod catalog          (default: "agentops")
AGENTOPS_VECTOR_SEARCH_ENDPOINT : Databricks Vector Search endpoint name
AGENTOPS_MODEL_SERVING_ENDPOINT : Model Serving endpoint name
AGENTOPS_MLFLOW_EXPERIMENT_BASE : Base path for MLflow experiments    (default: "/AgentOps")
AGENTOPS_LLM_ENDPOINT           : Databricks FM API endpoint name     (default: "databricks-meta-llama-3-3-70b-instruct")
AGENTOPS_EMBEDDING_ENDPOINT     : Embedding model endpoint name       (default: "databricks-bge-large-en")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentOpsConfig:
    """
    Single source of truth for all AgentOps framework configuration.

    Instantiate via `get_config()` for automatic env-var resolution,
    or construct directly for testing/overrides.
    """

    # --- Environment ---
    env: str = "dev"

    # --- Workspace ---
    workspace_host: str = ""

    # --- Unity Catalog ---
    dev_catalog: str = "agentops_dev"
    prod_catalog: str = "agentops_prod"
    dev_schema: str = "agentops"
    prod_schema: str = "agentops"

    # --- Vector Search ---
    vector_search_endpoint: str = "agentops_vs_endpoint"

    # --- Model Serving ---
    model_serving_endpoint: str = "agentops_endpoint"

    # --- MLflow ---
    mlflow_experiment_base: str = "/AgentOps"

    # --- LLM ---
    llm_endpoint: str = "databricks-meta-llama-3-3-70b-instruct"
    embedding_endpoint: str = "databricks-bge-large-en"

    # --- Derived properties (computed post-init) ---
    _active_catalog: str = field(init=False, repr=False, default="")
    _active_schema: str = field(init=False, repr=False, default="")

    def __post_init__(self) -> None:
        self._active_catalog = self.prod_catalog if self.env == "prod" else self.dev_catalog
        self._active_schema = self.prod_schema if self.env == "prod" else self.dev_schema

    @property
    def active_catalog(self) -> str:
        """The catalog for the current environment."""
        return self._active_catalog

    @property
    def active_schema(self) -> str:
        """The schema for the current environment."""
        return self._active_schema

    @property
    def active_catalog_schema(self) -> str:
        """Fully qualified `catalog.schema` for the current environment."""
        return f"{self.active_catalog}.{self.active_schema}"

    @property
    def mlflow_experiment_path(self) -> str:
        """Full MLflow experiment path for the current environment."""
        return f"{self.mlflow_experiment_base}/{self.env}"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def vector_search_index_name(self) -> str:
        """Fully qualified vector search index name."""
        return f"{self.active_catalog_schema}.agentops_vs_index"

    @property
    def chunks_table_name(self) -> str:
        """Fully qualified Delta table name for document chunks."""
        return f"{self.active_catalog_schema}.document_chunks"

    @property
    def eval_dataset_table_name(self) -> str:
        """Fully qualified Delta table name for evaluation datasets."""
        return f"{self.active_catalog_schema}.eval_datasets"

    @property
    def batch_results_table_name(self) -> str:
        """Fully qualified Delta table name for batch inference results."""
        return f"{self.active_catalog_schema}.batch_inference_results"

    def __str__(self) -> str:
        return (
            f"AgentOpsConfig(env={self.env}, "
            f"catalog={self.active_catalog}, "
            f"schema={self.active_schema}, "
            f"workspace={self.workspace_host or '<not set>'})"
        )


_config: Optional[AgentOpsConfig] = None


def get_config(reload: bool = False) -> AgentOpsConfig:
    """
    Return the singleton AgentOpsConfig, resolved from environment variables.

    Args:
        reload: Force re-read of environment variables.

    Returns:
        AgentOpsConfig populated from the current environment.

    Example:
        >>> config = get_config()
        >>> print(config.active_catalog_schema)
        agentops_dev.agentops
    """
    global _config
    if _config is None or reload:
        _config = AgentOpsConfig(
            env=os.environ.get("AGENTOPS_ENV", "dev"),
            workspace_host=os.environ.get("AGENTOPS_WORKSPACE_HOST", ""),
            dev_catalog=os.environ.get("AGENTOPS_DEV_CATALOG", "agentops_dev"),
            prod_catalog=os.environ.get("AGENTOPS_PROD_CATALOG", "agentops_prod"),
            dev_schema=os.environ.get("AGENTOPS_DEV_SCHEMA", "agentops"),
            prod_schema=os.environ.get("AGENTOPS_PROD_SCHEMA", "agentops"),
            vector_search_endpoint=os.environ.get(
                "AGENTOPS_VECTOR_SEARCH_ENDPOINT", "agentops_vs_endpoint"
            ),
            model_serving_endpoint=os.environ.get(
                "AGENTOPS_MODEL_SERVING_ENDPOINT", "agentops_endpoint"
            ),
            mlflow_experiment_base=os.environ.get(
                "AGENTOPS_MLFLOW_EXPERIMENT_BASE", "/AgentOps"
            ),
            llm_endpoint=os.environ.get(
                "AGENTOPS_LLM_ENDPOINT",
                "databricks-meta-llama-3-3-70b-instruct",
            ),
            embedding_endpoint=os.environ.get(
                "AGENTOPS_EMBEDDING_ENDPOINT", "databricks-bge-large-en"
            ),
        )
    return _config
