"""
AgentOps Redux Framework
========================
An opinionated, production-ready framework for developing, evaluating,
and promoting AI agents through dev → staging → prod on Databricks.

Key modules:
    config          - Environment-aware configuration (AgentOpsConfig)
    data_preparation - Data ingestion, chunking, vector search indexing
    agent_development - Agent base class, router, tool registry
    evaluation      - MLflow GenAI evaluation wrappers
    deployment      - Agent packaging and Model Serving deployment
    batch_inferencing - Spark-based batch inference
    utils           - MLflow, Unity Catalog, and Databricks SDK helpers
"""

from framework.config import AgentOpsConfig, get_config

__all__ = ["AgentOpsConfig", "get_config"]
