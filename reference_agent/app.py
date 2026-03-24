"""
Multi-Agent Application Entry Point
=====================================
The top-level mlflow.pyfunc model that wraps the AgentRouter for deployment.
This is what gets logged to MLflow, registered in Unity Catalog, and served
by the Databricks Model Serving endpoint.

The application receives OpenAI Chat Completion-style requests and routes
them through the AgentRouter to the appropriate specialized agent.

Input format:
    {
        "messages": [
            {"role": "user", "content": "What is the refund policy?"}
        ]
    }

Output format:
    {
        "role": "assistant",
        "content": "Based on the knowledge base, the refund policy states..."
    }

Deployment:
    >>> python reference_agent/app.py deploy
    # Logs model, registers in UC, sets @champion alias

Local test:
    >>> python reference_agent/app.py test
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

import mlflow
import mlflow.pyfunc

from framework.config import AgentOpsConfig, get_config
from framework.utils.mlflow_utils import setup_autologging, set_experiment_for_env
from reference_agent.router.router import build_router

logger = logging.getLogger(__name__)


class MultiAgentApp(mlflow.pyfunc.PythonModel):
    """
    Production-ready multi-agent application model.

    Wraps the AgentRouter as an mlflow.pyfunc.PythonModel so it can be:
      - Logged to MLflow with `mlflow.pyfunc.log_model()`
      - Registered in Unity Catalog
      - Served by a Databricks Model Serving endpoint
      - Loaded locally with `mlflow.pyfunc.load_model()`

    Example (local inference):
        >>> model = mlflow.pyfunc.load_model("models:/agentops_dev.agentops.multi_agent_app@champion")
        >>> result = model.predict({"messages": [{"role": "user", "content": "Hello"}]})
    """

    def __init__(self, config: Optional[AgentOpsConfig] = None) -> None:
        self.config = config or get_config()
        self._router = None

    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        """Called by MLflow when loading a saved model. Initializes the router."""
        self._router = build_router(config=self.config)
        setup_autologging(log_models=False)
        logger.info("MultiAgentApp loaded successfully")

    def predict(
        self,
        context: Optional[mlflow.pyfunc.PythonModelContext],
        model_input: Any,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Route the incoming request and return the agent's response.

        Args:
            context:     MLflow model context.
            model_input: {"messages": [{"role": "user", "content": "..."}]}
            params:      Optional inference parameters.

        Returns:
            {"role": "assistant", "content": "<response>"}
        """
        if self._router is None:
            self._router = build_router(config=self.config)

        return self._router.predict(context, model_input, params)


def deploy(
    config: Optional[AgentOpsConfig] = None,
    run_name: str = "multi_agent_app_deploy",
) -> str:
    """
    Log and register the MultiAgentApp in Unity Catalog.

    Args:
        config:   AgentOpsConfig instance.
        run_name: MLflow run name.

    Returns:
        Model URI (models:/catalog.schema.model@champion)

    Example:
        >>> uri = deploy()
        >>> print(uri)
        models:/agentops_dev.agentops.multi_agent_app@champion
    """
    cfg = config or get_config()
    registered_model_name = f"{cfg.active_catalog_schema}.multi_agent_app"

    setup_autologging(log_models=False)
    exp_id = set_experiment_for_env("multi_agent_app", cfg)

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tag("agentops.component", "app_deployment")
        mlflow.set_tag("agentops.env", cfg.env)

        app = MultiAgentApp(config=cfg)

        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=app,
            pip_requirements=[
                "mlflow>=2.17.0",
                "databricks-sdk>=0.30.0",
                "databricks-langchain>=0.3.0",
                "langchain>=0.3.0",
                "langchain-core>=0.3.0",
            ],
            registered_model_name=registered_model_name,
            metadata={
                "app_name": "multi_agent_app",
                "agentops_env": cfg.env,
                "agents": "rag_agent,summarization_agent",
            },
        )

    # Set @champion alias
    from mlflow.tracking import MlflowClient
    client = MlflowClient()
    client.set_registered_model_alias(
        name=registered_model_name,
        alias="champion",
        version=str(model_info.registered_model_version),
    )

    champion_uri = f"models:/{registered_model_name}@champion"
    logger.info("Deployed MultiAgentApp → %s (run: %s)", champion_uri, run.info.run_id[:8])
    return champion_uri


def test_local(config: Optional[AgentOpsConfig] = None) -> None:
    """
    Run a quick local smoke test without a Databricks workspace.
    Tests the predict interface but not the actual LLM/VS calls.
    """
    cfg = config or get_config()
    app = MultiAgentApp(config=cfg)
    app._router = build_router(config=cfg)

    test_inputs = [
        {"messages": [{"role": "user", "content": "What is the main purpose of this system?"}]},
        {"messages": [{"role": "user", "content": "Summarize: This is a test document about AI agents."}]},
    ]

    for i, input_data in enumerate(test_inputs):
        print(f"\n--- Test {i + 1} ---")
        print(f"Input: {input_data['messages'][0]['content']}")
        try:
            result = app.predict(None, input_data)
            print(f"Output: {result}")
        except Exception as e:
            print(f"Error (expected in local env without VS): {e}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "test"

    if command == "deploy":
        os.environ.setdefault("AGENTOPS_ENV", "dev")
        uri = deploy()
        print(f"Deployed: {uri}")
    elif command == "test":
        test_local()
    else:
        print(f"Unknown command: {command}. Use 'deploy' or 'test'.")
