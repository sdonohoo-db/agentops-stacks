"""
Agent Router
============
Multi-agent router that classifies incoming requests and dispatches
them to the appropriate specialized agent.

The router is the single entry point for the multi-agent application.
Client code calls the router; the router decides which agent handles
each request. This design makes it easy to add new agents without
changing the client interface.

Router classification uses the LLM (via Databricks FM API) to categorize
the intent of each incoming message, then routes to the matching agent.

Architecture:
    Client → AgentRouter → Agent1 (RAG/Q&A)
                        → Agent2 (Summarization)
                        → Agent3 (... future)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import mlflow

from framework.agent_development.agent_base import AgentBase
from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


ROUTER_SYSTEM_PROMPT = """You are a request routing assistant. Given a user message,
classify it into exactly one of the following categories based on the user's intent.

Available categories:
{categories}

Return ONLY the category name, nothing else.

Examples:
- "What is the company's vacation policy?" → {first_category}
- "Summarize this document for me" → {second_category}
"""


class AgentRouter(AgentBase):
    """
    Routes incoming requests to specialized agents based on intent classification.

    Register agents with `register_agent()`, then call `predict()` to route.
    The router uses an LLM to classify intent and dispatch to the right agent.

    Example:
        >>> from reference_agent.agents.agent1.agent import RAGAgent
        >>> from reference_agent.agents.agent2.agent import SummarizationAgent
        >>>
        >>> router = AgentRouter()
        >>> router.register_agent(
        ...     name="qa",
        ...     agent=RAGAgent(),
        ...     description="Handles questions that require looking up specific information",
        ...     keywords=["what", "how", "explain", "tell me about"],
        ... )
        >>> router.register_agent(
        ...     name="summarize",
        ...     agent=SummarizationAgent(),
        ...     description="Summarizes long documents or conversations",
        ...     keywords=["summarize", "summary", "tldr", "overview"],
        ... )
        >>> result = router.predict(None, {"messages": [{"role": "user", "content": "Summarize this..."}]})
    """

    def __init__(
        self,
        llm_endpoint: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        super().__init__(
            name="agent_router",
            description="Routes requests to the appropriate specialized agent",
            config=config,
        )
        self._registered_agents: Dict[str, Dict[str, Any]] = {}
        self._llm_endpoint = llm_endpoint or self.config.llm_endpoint
        self._llm: Optional[ChatDatabricks] = None

    @property
    def llm(self):
        if self._llm is None:
            from langchain_databricks import ChatDatabricks
            self._llm = ChatDatabricks(
                endpoint=self._llm_endpoint,
                temperature=0.0,
                max_tokens=20,
            )
        return self._llm

    def register_agent(
        self,
        name: str,
        agent: AgentBase,
        description: str,
        keywords: Optional[List[str]] = None,
    ) -> None:
        """
        Register a specialized agent with the router.

        Args:
            name:        Short identifier for routing (e.g., "qa", "summarize").
            agent:       AgentBase instance to route to.
            description: Natural language description of when to route here.
            keywords:    Optional trigger keywords for fast-path routing.

        Example:
            >>> router.register_agent("qa", rag_agent, "Answers factual questions about company policies")
        """
        self._registered_agents[name] = {
            "agent": agent,
            "description": description,
            "keywords": [k.lower() for k in (keywords or [])],
        }
        logger.info("Registered agent '%s': %s", name, description)

    def _classify_intent(self, user_message: str) -> str:
        """
        Use LLM to classify the user's intent and return an agent name.

        First tries keyword matching (fast path), then falls back to LLM
        classification if no keywords match.
        """
        lower_msg = user_message.lower()

        # Fast path: keyword matching
        for agent_name, info in self._registered_agents.items():
            for keyword in info["keywords"]:
                if keyword in lower_msg:
                    logger.debug("Keyword match: '%s' → agent '%s'", keyword, agent_name)
                    return agent_name

        # LLM classification
        if not self._registered_agents:
            raise ValueError("No agents registered with the router.")

        categories = "\n".join(
            f"- {name}: {info['description']}"
            for name, info in self._registered_agents.items()
        )
        agent_names = list(self._registered_agents.keys())

        prompt = ROUTER_SYSTEM_PROMPT.format(
            categories=categories,
            first_category=agent_names[0],
            second_category=agent_names[1] if len(agent_names) > 1 else agent_names[0],
        )

        from langchain_core.messages import HumanMessage, SystemMessage
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=user_message),
        ])
        classified = response.content.strip().lower()

        # Match to a registered agent name
        for agent_name in self._registered_agents:
            if agent_name.lower() in classified:
                logger.debug("LLM classified '%s...' → agent '%s'", user_message[:50], agent_name)
                return agent_name

        # Default to first registered agent
        default = agent_names[0]
        logger.warning(
            "Could not classify intent '%s...'; defaulting to '%s'",
            user_message[:50],
            default,
        )
        return default

    @mlflow.trace(name="router.invoke", span_type="AGENT")
    def _invoke(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Any] = None,
    ) -> str:
        """
        Classify the user's intent and dispatch to the appropriate agent.

        Extracts the last user message, classifies intent, routes to the
        matching agent, and returns its response.
        """
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return "Please provide a message."

        last_user_message = user_messages[-1].get("content", "")

        with mlflow.start_span(name="intent_classification", span_type="LLM"):
            target_agent_name = self._classify_intent(last_user_message)
            mlflow.set_tag("routed_to", target_agent_name)

        target = self._registered_agents[target_agent_name]["agent"]

        with mlflow.start_span(name=f"agent.{target_agent_name}", span_type="AGENT"):
            result = target.predict(context, {"messages": messages})

        return result.get("content", str(result))
