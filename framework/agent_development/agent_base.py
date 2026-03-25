"""
Agent Base Class
================
Base class for all AgentOps agents. Extends `mlflow.pyfunc.PythonModel`
to ensure every agent is MLflow-compatible from day one.

Guarantees:
  1. Consistent predict() interface (OpenAI Chat Completion format)
  2. Automatic MLflow tracing via @mlflow.trace
  3. UC model registration via save()
  4. Environment-aware catalog/endpoint resolution via AgentOpsConfig

All agents in the framework inherit from AgentBase. The reference agent
demonstrates the full pattern; copy it as a starting point for new agents.

Predict interface (input):
    {
        "messages": [
            {"role": "user", "content": "What is the refund policy?"}
        ]
    }

Predict interface (output):
    {
        "content": "Our refund policy allows...",
        "role": "assistant"
    }
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

import mlflow
import mlflow.pyfunc
import pandas as pd

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


class AgentBase(mlflow.pyfunc.PythonModel):
    """
    Abstract base class for all AgentOps agents.

    Subclass and implement `_invoke()` to define agent behavior.
    Everything else (tracing, logging, packaging) is handled here.

    Minimal example:
        >>> class MyAgent(AgentBase):
        ...     def _invoke(self, messages, context=None):
        ...         # your LLM call here
        ...         return "Hello from MyAgent"
        ...
        >>> agent = MyAgent(name="my_agent")
        >>> result = agent.predict(None, {"messages": [{"role": "user", "content": "Hi"}]})
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        """
        Args:
            name:        Short identifier (e.g., "rag_agent"). Used in MLflow runs and UC.
            description: Human-readable description of this agent's purpose.
            config:      AgentOpsConfig. Defaults to get_config().
        """
        self.name = name
        self.description = description
        self.config = config or get_config()
        self._chain = None  # Subclasses set this to their LangChain chain/graph

    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        """
        Called by MLflow when loading a saved model from UC.
        Subclasses can override to load artifacts from context.artifacts.
        """
        pass

    @abstractmethod
    def _invoke(
        self,
        messages: List[Dict[str, str]],
        context: Optional[mlflow.pyfunc.PythonModelContext] = None,
    ) -> str:
        """
        Core agent logic. Subclasses implement this.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": str}
            context:  MLflow model context (for artifact access during serving).

        Returns:
            Response string from the agent.
        """
        ...

    @mlflow.trace(name="agent.predict", span_type="AGENT")
    def predict(
        self,
        context: Optional[mlflow.pyfunc.PythonModelContext],
        model_input: list[Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        MLflow pyfunc predict interface. Handles both DataFrame and dict inputs.

        Args:
            context:     MLflow context (for artifact paths).
            model_input: One of:
                         - dict: {"messages": [...]}
                         - pd.DataFrame: with "messages" column
                         - list: [{"role": ..., "content": ...}]
            params:      Optional inference parameters (unused by default).

        Returns:
            {"role": "assistant", "content": "<response>"}
        """
        messages = self._extract_messages(model_input)
        if mlflow.active_run():
            mlflow.log_param("agent_name", self.name)

        response = self._invoke(messages, context)
        return {"role": "assistant", "content": response}

    def _extract_messages(self, model_input: Any) -> List[Dict[str, str]]:
        """Normalize diverse input formats into a messages list."""
        if isinstance(model_input, pd.DataFrame):
            row = model_input.iloc[0]
            return row.get("messages", [{"role": "user", "content": str(row.get("content", ""))}])
        if isinstance(model_input, dict):
            return model_input.get("messages", [{"role": "user", "content": str(model_input)}])
        if isinstance(model_input, list):
            return model_input
        return [{"role": "user", "content": str(model_input)}]

    def save(
        self,
        artifact_path: str = "model",
        registered_model_name: Optional[str] = None,
        pip_requirements: Optional[List[str]] = None,
        extra_pip_requirements: Optional[List[str]] = None,
    ) -> str:
        """
        Log this agent to MLflow and optionally register it in Unity Catalog.

        Args:
            artifact_path:          MLflow artifact path (default: "model").
            registered_model_name:  UC model name to register as.
                                    Defaults to {active_catalog_schema}.{name}
            pip_requirements:       Full pip requirements list.
            extra_pip_requirements: Additional packages beyond auto-detected.

        Returns:
            Model URI (e.g., "models:/agentops_dev.agentops.rag_agent/1")

        Example:
            >>> with mlflow.start_run():
            ...     model_uri = agent.save()
        """
        uc_name = registered_model_name or f"{self.config.active_catalog_schema}.{self.name}"

        reqs = pip_requirements or [
            "mlflow>=2.17.0",
            "databricks-langchain>=0.3.0",
            "databricks-sdk>=0.30.0",
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
        ]

        model_info = mlflow.pyfunc.log_model(
            artifact_path=artifact_path,
            python_model=self,
            pip_requirements=reqs,
            extra_pip_requirements=extra_pip_requirements,
            registered_model_name=uc_name,
            metadata={
                "agent_name": self.name,
                "agent_description": self.description,
                "agentops_env": self.config.env,
            },
        )

        logger.info(
            "Saved agent '%s' → %s (version %s)",
            self.name,
            uc_name,
            model_info.registered_model_version,
        )
        return model_info.model_uri

    def set_champion_alias(self, version: Optional[str] = None) -> None:
        """
        Set the @champion alias on the latest (or specified) model version.

        The @champion alias is what production deployment targets.
        Only call this after validation tests have passed.

        Args:
            version: Model version number string. If None, uses latest.

        Example:
            >>> agent.set_champion_alias()  # promotes latest to @champion
        """
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        uc_name = f"{self.config.active_catalog_schema}.{self.name}"

        if version is None:
            versions = client.search_model_versions(f"name='{uc_name}'")
            if not versions:
                raise ValueError(f"No versions found for model '{uc_name}'")
            version = max(versions, key=lambda v: int(v.version)).version

        client.set_registered_model_alias(
            name=uc_name,
            alias="champion",
            version=version,
        )
        logger.info("Set @champion alias on %s version %s", uc_name, version)
