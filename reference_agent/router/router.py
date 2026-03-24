"""
Reference Multi-Agent Router
=============================
Concrete router implementation for the reference multi-agent application.
Routes between the RAG Q&A agent (Agent 1) and Summarization agent (Agent 2).

This file shows the standard pattern for wiring agents into the router.
For new agent projects, copy this file and add/swap agent registrations.

Routing logic:
  - Keyword fast-path: matches common intent keywords without LLM call
  - LLM fallback: uses ChatDatabricks to classify ambiguous intent

Example:
    >>> router = build_router()
    >>> result = router.predict(None, {
    ...     "messages": [{"role": "user", "content": "What is the leave policy?"}]
    ... })
    >>> print(result["content"])
"""

from __future__ import annotations

from typing import Optional

from framework.agent_development.router import AgentRouter
from framework.config import AgentOpsConfig, get_config
from reference_agent.agents.agent1.agent import RAGAgent
from reference_agent.agents.agent2.agent import SummarizationAgent


def build_router(config: Optional[AgentOpsConfig] = None) -> AgentRouter:
    """
    Build and configure the multi-agent router with all registered agents.

    This is the factory function that assembles the full application.
    Call this in app.py to create the deployable router.

    Args:
        config: AgentOpsConfig instance. Defaults to get_config().

    Returns:
        Configured AgentRouter ready for prediction.

    Example:
        >>> router = build_router()
        >>> result = router.predict(None, {
        ...     "messages": [{"role": "user", "content": "Summarize this document..."}]
        ... })
    """
    cfg = config or get_config()
    router = AgentRouter(config=cfg)

    # Register Agent 1: RAG Q&A
    router.register_agent(
        name="rag_agent",
        agent=RAGAgent(config=cfg),
        description=(
            "Handles questions that require looking up specific information from the "
            "knowledge base. Best for: factual questions, policy lookups, 'what is', "
            "'how does', 'tell me about' queries."
        ),
        keywords=[
            "what", "how", "explain", "tell me", "describe",
            "find", "search", "show", "list", "who", "when", "where",
            "what is", "what are", "can you explain",
        ],
    )

    # Register Agent 2: Summarization
    router.register_agent(
        name="summarization_agent",
        agent=SummarizationAgent(config=cfg),
        description=(
            "Creates concise summaries of documents, reports, or long-form content. "
            "Best for: 'summarize', 'give me a summary', 'tldr', 'overview', "
            "'what are the key points' requests."
        ),
        keywords=[
            "summarize", "summary", "tldr", "overview", "brief",
            "condense", "shorten", "key points", "main points",
            "give me a summary", "can you summarize",
        ],
    )

    return router
