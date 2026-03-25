"""
App Deployment
==============
Create and update Databricks Model Serving endpoints for the
multi-agent application.

The Model Serving endpoint is the live interface that:
  - Serves real-time inference for end users
  - Is called by SME reviewers during development testing
  - Is called by Batch Inferencing for offline workloads

Endpoint naming: Uses config.model_serving_endpoint, which is
environment-specific (set by DAB variables).

Guardrails:
    AI Gateway guardrails can be attached at endpoint creation or update
    time. Guardrails filter both input (prompt injection, PII) and output
    (harmful content) without requiring changes to agent code.

Canary deployments:
    Use enable_canary=True with canary_traffic_percentage to route a
    fraction of traffic to a new model version for A/B testing before
    full promotion.

Reference:
    https://docs.databricks.com/en/machine-learning/model-serving/create-manage-serving-endpoints.html
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class EndpointDeploymentResult:
    """Result from endpoint deployment."""
    endpoint_name: str
    endpoint_url: str
    state: str
    model_name: str
    model_version: str
    errors: List[str]
    canary_traffic_percentage: Optional[int] = None
    guardrails_enabled: bool = False

    @property
    def success(self) -> bool:
        return self.state == "READY" and len(self.errors) == 0


class AppDeployer:
    """
    Deploy or update the multi-agent application Model Serving endpoint.

    Handles the full endpoint lifecycle:
      - Create endpoint if it doesn't exist
      - Update served entities if endpoint exists
      - Wait for endpoint to reach READY state
      - Return the endpoint URL for manifest generation
      - Optionally attach AI Gateway guardrails (input/output safety, PII filtering)
      - Optionally configure canary traffic splits for safe rollouts

    Example:
        >>> deployer = AppDeployer()
        >>> result = deployer.deploy(
        ...     model_name="agentops_dev.agentops.multi_agent_app",
        ...     model_alias="champion",
        ...     enable_guardrails=True,
        ...     rate_limit_per_minute=60,
        ... )
        >>> print(f"Endpoint ready at: {result.endpoint_url}")
    """

    def __init__(
        self,
        endpoint_name: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        self.config = config or get_config()
        self.endpoint_name = endpoint_name or self.config.model_serving_endpoint

    def _get_client(self):
        from databricks.sdk import WorkspaceClient
        return WorkspaceClient()

    def deploy(
        self,
        model_name: str,
        model_alias: str = "champion",
        scale_to_zero: bool = True,
        workload_size: str = "Small",
        wait_for_ready: bool = True,
        timeout_seconds: int = 600,
        enable_guardrails: bool = False,
        rate_limit_per_minute: Optional[int] = None,
        enable_canary: bool = False,
        canary_traffic_percentage: int = 10,
        canary_model_alias: str = "challenger",
    ) -> EndpointDeploymentResult:
        """
        Create or update the Model Serving endpoint.

        Args:
            model_name:                UC model name (e.g., "catalog.schema.model").
            model_alias:               Model alias to serve (default: "champion").
            scale_to_zero:             Allow endpoint to scale to zero when idle.
                                       Set False for production (no cold starts).
            workload_size:             Endpoint size: "Small", "Medium", "Large".
            wait_for_ready:            Block until endpoint is READY.
            timeout_seconds:           Max wait time.
            enable_guardrails:         Attach AI Gateway input/output safety guardrails.
                                       Filters prompt injection, PII, and harmful content.
            rate_limit_per_minute:     Max requests per minute via AI Gateway rate limiting.
                                       None disables rate limiting.
            enable_canary:             Route a fraction of traffic to a second model version
                                       for A/B testing before full promotion.
            canary_traffic_percentage: Percent of traffic routed to canary (default 10).
            canary_model_alias:        Alias of the canary model version (default "challenger").

        Returns:
            EndpointDeploymentResult with endpoint URL, state, and guardrail info.

        Example:
            >>> # Production deploy with guardrails + rate limiting
            >>> result = deployer.deploy(
            ...     model_name="agentops_prod.agentops.multi_agent_app",
            ...     scale_to_zero=False,
            ...     workload_size="Medium",
            ...     enable_guardrails=True,
            ...     rate_limit_per_minute=120,
            ... )

            >>> # Canary rollout: 10% traffic to challenger version
            >>> result = deployer.deploy(
            ...     model_name="agentops_prod.agentops.multi_agent_app",
            ...     enable_canary=True,
            ...     canary_traffic_percentage=10,
            ...     canary_model_alias="challenger",
            ... )
        """
        client = self._get_client()

        champion_version = self._get_version_for_alias(model_name, model_alias)

        if enable_canary:
            served_entities = self._build_canary_served_entities(
                model_name=model_name,
                champion_version=champion_version,
                canary_traffic_percentage=canary_traffic_percentage,
                canary_model_alias=canary_model_alias,
                workload_size=workload_size,
                scale_to_zero=scale_to_zero,
            )
        else:
            served_entities = [
                {
                    "entity_name": model_name,
                    "entity_version": champion_version,
                    "workload_size": workload_size,
                    "scale_to_zero_enabled": scale_to_zero,
                    "traffic_percentage": 100,
                }
            ]

        try:
            client.serving_endpoints.get(name=self.endpoint_name)
            logger.info("Updating existing endpoint '%s'...", self.endpoint_name)
            client.serving_endpoints.update_config(
                name=self.endpoint_name,
                served_entities=served_entities,
            )
        except Exception:
            logger.info("Creating endpoint '%s'...", self.endpoint_name)
            from databricks.sdk.service.serving import EndpointCoreConfigInput
            client.serving_endpoints.create(
                name=self.endpoint_name,
                config=EndpointCoreConfigInput(served_entities=served_entities),
            )

        if enable_guardrails or rate_limit_per_minute is not None:
            self._configure_ai_gateway(
                client=client,
                enable_guardrails=enable_guardrails,
                rate_limit_per_minute=rate_limit_per_minute,
            )

        if wait_for_ready:
            state = self._wait_for_ready(client, timeout_seconds)
        else:
            state = "UPDATING"

        endpoint_url = self._get_endpoint_url()

        return EndpointDeploymentResult(
            endpoint_name=self.endpoint_name,
            endpoint_url=endpoint_url,
            state=state,
            model_name=model_name,
            model_version=str(champion_version),
            errors=[],
            canary_traffic_percentage=canary_traffic_percentage if enable_canary else None,
            guardrails_enabled=enable_guardrails,
        )

    def _build_canary_served_entities(
        self,
        model_name: str,
        champion_version: str,
        canary_traffic_percentage: int,
        canary_model_alias: str,
        workload_size: str,
        scale_to_zero: bool,
    ) -> List[Dict[str, Any]]:
        """Build served_entities list for a canary traffic split."""
        champion_traffic = 100 - canary_traffic_percentage
        canary_version = self._get_version_for_alias(model_name, canary_model_alias)

        logger.info(
            "Canary split: %d%% champion (v%s) / %d%% challenger (v%s)",
            champion_traffic, champion_version,
            canary_traffic_percentage, canary_version,
        )

        return [
            {
                "entity_name": model_name,
                "entity_version": champion_version,
                "name": "champion",
                "workload_size": workload_size,
                "scale_to_zero_enabled": scale_to_zero,
                "traffic_percentage": champion_traffic,
            },
            {
                "entity_name": model_name,
                "entity_version": canary_version,
                "name": "challenger",
                "workload_size": workload_size,
                "scale_to_zero_enabled": scale_to_zero,
                "traffic_percentage": canary_traffic_percentage,
            },
        ]

    def _configure_ai_gateway(
        self,
        client: Any,
        enable_guardrails: bool,
        rate_limit_per_minute: Optional[int],
    ) -> None:
        """
        Attach AI Gateway configuration to the endpoint.

        Guardrails filter:
          - Input: prompt injection detection, PII redaction (email, phone, SSN, etc.)
          - Output: harmful content filtering (violence, hate speech, etc.)

        Rate limiting: enforced per-endpoint, per-user or per-IP depending on config.
        """
        from databricks.sdk.service.serving import (
            AiGatewayConfig,
            AiGatewayGuardrails,
            AiGatewayGuardrailParameters,
            AiGatewayGuardrailPiiBehavior,
            AiGatewayGuardrailPiiBehaviorBehavior,
            AiGatewayRateLimit,
            AiGatewayRateLimitRenewalPeriod,
        )

        guardrails_config = None
        if enable_guardrails:
            pii_behavior = AiGatewayGuardrailPiiBehavior(
                behavior=AiGatewayGuardrailPiiBehaviorBehavior.BLOCK,
            )
            input_guardrail = AiGatewayGuardrailParameters(
                pii=pii_behavior,
                safety=True,
            )
            output_guardrail = AiGatewayGuardrailParameters(
                safety=True,
            )
            guardrails_config = AiGatewayGuardrails(
                input=input_guardrail,
                output=output_guardrail,
            )
            logger.info("AI Gateway guardrails enabled (PII blocking + safety filtering).")

        rate_limits = None
        if rate_limit_per_minute is not None:
            rate_limits = [
                AiGatewayRateLimit(
                    calls=rate_limit_per_minute,
                    renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE,
                )
            ]
            logger.info("AI Gateway rate limit: %d req/min.", rate_limit_per_minute)

        gateway_config = AiGatewayConfig(
            guardrails=guardrails_config,
            rate_limits=rate_limits,
        )

        client.serving_endpoints.put_ai_gateway(
            name=self.endpoint_name,
            guardrails=gateway_config.guardrails,
            rate_limits=gateway_config.rate_limits,
        )
        logger.info("AI Gateway configured for endpoint '%s'.", self.endpoint_name)

    def promote_canary(self) -> EndpointDeploymentResult:
        """
        Promote the challenger to 100% traffic, retiring the canary split.

        Call this after a successful canary soak period.

        Example:
            >>> deployer.promote_canary()
        """
        client = self._get_client()
        endpoint = client.serving_endpoints.get(name=self.endpoint_name)

        # Find the challenger served entity
        challenger = None
        for entity in (endpoint.config.served_entities or []):
            if entity.name == "challenger":
                challenger = entity
                break

        if challenger is None:
            raise ValueError(
                f"No 'challenger' served entity found on endpoint '{self.endpoint_name}'. "
                "Deploy with enable_canary=True first."
            )

        logger.info(
            "Promoting challenger (version %s) to 100%% traffic on '%s'.",
            challenger.entity_version, self.endpoint_name,
        )

        client.serving_endpoints.update_config(
            name=self.endpoint_name,
            served_entities=[
                {
                    "entity_name": challenger.entity_name,
                    "entity_version": challenger.entity_version,
                    "name": "champion",
                    "workload_size": challenger.workload_size,
                    "scale_to_zero_enabled": challenger.scale_to_zero_enabled,
                    "traffic_percentage": 100,
                }
            ],
        )

        state = self._wait_for_ready(client, timeout_seconds=300)
        return EndpointDeploymentResult(
            endpoint_name=self.endpoint_name,
            endpoint_url=self._get_endpoint_url(),
            state=state,
            model_name=challenger.entity_name,
            model_version=str(challenger.entity_version),
            errors=[],
        )

    def _wait_for_ready(
        self,
        client: Any,
        timeout_seconds: int,
    ) -> str:
        elapsed = 0
        while elapsed < timeout_seconds:
            endpoint = client.serving_endpoints.get(name=self.endpoint_name)
            state = endpoint.state.config_update.value if endpoint.state.config_update else "UNKNOWN"
            if state == "NOT_UPDATING":
                # Check if ready
                ready_state = endpoint.state.ready.value if endpoint.state.ready else "NOT_READY"
                if ready_state == "READY":
                    logger.info("Endpoint '%s' is READY.", self.endpoint_name)
                    return "READY"
            logger.debug("Endpoint state: %s (elapsed %ds)", state, elapsed)
            time.sleep(15)
            elapsed += 15
        raise TimeoutError(f"Endpoint '{self.endpoint_name}' did not become READY in {timeout_seconds}s")

    def _get_endpoint_url(self) -> str:
        workspace_url = self.config.workspace_host.rstrip("/")
        return f"{workspace_url}/serving-endpoints/{self.endpoint_name}/invocations"

    def _get_version_for_alias(self, model_name: str, alias: str) -> str:
        try:
            from mlflow.tracking import MlflowClient
            client = MlflowClient()
            version = client.get_model_version_by_alias(model_name, alias)
            return version.version
        except Exception:
            return "latest"

    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a test inference call to the endpoint.

        Args:
            input_data: Request body (OpenAI Chat format).

        Returns:
            Response dict from the endpoint.

        Example:
            >>> result = deployer.invoke({
            ...     "messages": [{"role": "user", "content": "Hello"}]
            ... })
        """
        import requests
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient()
        token = client.config.authenticate()["Authorization"].split(" ")[1]

        endpoint_url = self._get_endpoint_url()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        import json
        response = requests.post(
            endpoint_url,
            headers=headers,
            data=json.dumps({"messages": input_data.get("messages", [])}),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
