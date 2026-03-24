"""
Agent Deployment
================
Log agents to MLflow and register them in Unity Catalog with the
@champion alias that production serving targets.

Deployment flow:
    1. Log model to MLflow (mlflow.pyfunc.log_model)
    2. Register in Unity Catalog (mlflow.register_model)
    3. Set @champion alias on the registered version
    4. Optionally set @challenger for A/B testing

The @champion alias is the convention that Model Serving endpoints use
to always serve the latest promoted version without needing to update
endpoint configs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result from an agent deployment operation."""
    model_uri: str
    registered_model_name: str
    version: str
    alias: str
    run_id: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class AgentDeployer:
    """
    Package an agent, log it to MLflow, register in Unity Catalog,
    and promote via alias.

    Example:
        >>> from reference_agent.app import MultiAgentApp
        >>> deployer = AgentDeployer(agent_name="rag_agent")
        >>> result = deployer.deploy(
        ...     agent=RAGAgent(),
        ...     pip_requirements=["mlflow>=2.17.0", "databricks-langchain>=0.3.0"],
        ... )
        >>> print(f"Deployed: {result.model_uri}")
    """

    def __init__(
        self,
        agent_name: str,
        registered_model_name: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        """
        Args:
            agent_name:             Short name (e.g., "rag_agent").
            registered_model_name:  UC model name override. Defaults to
                                    {active_catalog_schema}.{agent_name}
            config:                 AgentOpsConfig instance.
        """
        self.config = config or get_config()
        self.agent_name = agent_name
        self.registered_model_name = (
            registered_model_name
            or f"{self.config.active_catalog_schema}.{agent_name}"
        )

    def deploy(
        self,
        agent: Any,
        pip_requirements: Optional[List[str]] = None,
        run_name: Optional[str] = None,
        alias: str = "champion",
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> DeploymentResult:
        """
        Log, register, and alias an agent.

        Args:
            agent:            The agent object (AgentBase, LangChain chain,
                              or any mlflow.pyfunc.PythonModel subclass).
            pip_requirements: Python package requirements for the model.
            run_name:         MLflow run name. Defaults to "{agent_name}_deploy".
            alias:            UC model alias to set (default: "champion").
            extra_metadata:   Additional metadata tags for the model.

        Returns:
            DeploymentResult with model URI and UC details.

        Example:
            >>> result = deployer.deploy(agent=my_agent)
            >>> print(result.model_uri)
            models:/agentops_dev.agentops.rag_agent@champion
        """
        run_name = run_name or f"{self.agent_name}_deploy_{self.config.env}"
        reqs = pip_requirements or self._default_requirements()
        metadata = {
            "agent_name": self.agent_name,
            "agentops_env": self.config.env,
            **(extra_metadata or {}),
        }

        try:
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.set_tag("agentops.deploy_type", "agent")
                mlflow.set_tag("agentops.agent_name", self.agent_name)

                # Log the model
                model_info = mlflow.pyfunc.log_model(
                    artifact_path="model",
                    python_model=agent,
                    pip_requirements=reqs,
                    registered_model_name=self.registered_model_name,
                    metadata=metadata,
                )

                version = model_info.registered_model_version
                run_id = run.info.run_id

            # Set alias (must be outside start_run for some backends)
            self._set_alias(version, alias)

            model_uri = f"models:/{self.registered_model_name}@{alias}"
            logger.info(
                "Deployed '%s' version %s → %s",
                self.agent_name, version, model_uri,
            )

            return DeploymentResult(
                model_uri=model_uri,
                registered_model_name=self.registered_model_name,
                version=str(version),
                alias=alias,
                run_id=run_id,
                errors=[],
            )

        except Exception as e:
            logger.error("Deployment failed for '%s': %s", self.agent_name, e)
            return DeploymentResult(
                model_uri="",
                registered_model_name=self.registered_model_name,
                version="",
                alias=alias,
                run_id="",
                errors=[str(e)],
            )

    def _set_alias(self, version: str, alias: str) -> None:
        client = MlflowClient()
        client.set_registered_model_alias(
            name=self.registered_model_name,
            alias=alias,
            version=str(version),
        )
        logger.info(
            "Set @%s alias on %s version %s", alias, self.registered_model_name, version
        )

    def _default_requirements(self) -> List[str]:
        return [
            "mlflow>=2.17.0",
            "databricks-sdk>=0.30.0",
            "databricks-langchain>=0.3.0",
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
        ]

    def get_latest_version(self) -> Optional[str]:
        """Return the latest version number for the registered model."""
        client = MlflowClient()
        try:
            versions = client.search_model_versions(
                f"name='{self.registered_model_name}'"
            )
            if not versions:
                return None
            return max(versions, key=lambda v: int(v.version)).version
        except Exception:
            return None

    def get_champion_uri(self) -> str:
        """Return the @champion model URI for this agent."""
        return f"models:/{self.registered_model_name}@champion"
