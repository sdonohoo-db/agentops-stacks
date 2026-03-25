"""
Summarization Agent (Agent 2)
==============================
Summarizes documents, conversations, or any long-form text content.
Uses structured output to ensure summaries follow a consistent format:
main topic, key points, and conclusion.

This is Agent 2 in the reference multi-agent application.

The summarization agent does not use vector search — it summarizes
content provided directly in the message (or retrieved by the router).

Example:
    >>> agent = SummarizationAgent()
    >>> result = agent.predict(None, {
    ...     "messages": [
    ...         {"role": "user", "content": "Summarize: [long document text...]"}
    ...     ]
    ... })
    >>> print(result["content"])
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import mlflow
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_databricks import ChatDatabricks

from framework.agent_development.agent_base import AgentBase
from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


SUMMARIZATION_SYSTEM_PROMPT = """You are a professional summarization assistant.

Create a clear, concise summary of the provided content using this structure:

**Main Topic**: [One sentence describing what this is about]

**Key Points**:
- [Key point 1]
- [Key point 2]
- [Key point 3]
- [Add more if needed, up to 5 points]

**Conclusion**: [1-2 sentences on takeaways or significance]

Be concise — target {max_length} words or fewer for the full summary.
Do not add information not present in the content."""

SUMMARIZATION_HUMAN_PROMPT = "Please summarize the following:\n\n{content}"


class SummarizationAgent(AgentBase):
    """
    Structured summarization agent for documents and conversations.

    Produces consistently formatted summaries with topic, key points,
    and conclusion sections. Uses the Databricks Foundation Model API.

    This is Agent 2 in the reference multi-agent application.

    Example:
        >>> agent = SummarizationAgent(max_summary_length=300)
        >>> result = agent.predict(None, {
        ...     "messages": [{"role": "user", "content": "Summarize this: ..."}]
        ... })
    """

    def __init__(
        self,
        max_summary_length: int = 500,
        llm_endpoint: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
    ) -> None:
        super().__init__(
            name="summarization_agent",
            description="Creates structured summaries of documents and conversations",
            config=config,
        )
        self.max_summary_length = max_summary_length
        self._llm_endpoint = llm_endpoint or self.config.llm_endpoint
        self._chain = None

    def _build_chain(self):
        """Build the summarization chain (lazy initialization)."""
        llm = ChatDatabricks(
            endpoint=self._llm_endpoint,
            temperature=0.2,
            max_tokens=1024,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SUMMARIZATION_SYSTEM_PROMPT),
            ("human", SUMMARIZATION_HUMAN_PROMPT),
        ])

        return prompt | llm | StrOutputParser()

    @property
    def chain(self):
        if self._chain is None:
            self._chain = self._build_chain()
        return self._chain

    def _extract_content_to_summarize(
        self, messages: List[Dict[str, str]]
    ) -> str:
        """
        Extract the content to summarize from the messages list.

        Looks for explicit summarization requests. Handles:
        - "Summarize: <content>"
        - "Please summarize <content>"
        - Multi-turn: combines all user messages as the content
        """
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return ""

        last_msg = user_messages[-1].get("content", "")

        # Strip summarize prefix if present
        import re
        prefixes = [
            r"^summarize[:\s]+",
            r"^please summarize[:\s]+",
            r"^give me a summary of[:\s]+",
            r"^tldr[:\s]+",
        ]
        for prefix in prefixes:
            cleaned = re.sub(prefix, "", last_msg, flags=re.IGNORECASE).strip()
            if len(cleaned) < len(last_msg) - 5:  # prefix was stripped
                return cleaned

        return last_msg

    @mlflow.trace(name="summarization_agent.invoke", span_type="AGENT")
    def _invoke(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Any] = None,
    ) -> str:
        """
        Generate a structured summary of the provided content.
        """
        content = self._extract_content_to_summarize(messages)
        if not content:
            return "Please provide content to summarize."

        mlflow.langchain.autolog(log_traces=True, disable=False)

        response = self.chain.invoke({
            "max_length": self.max_summary_length,
            "content": content,
        })

        mlflow.log_metric("summarization.content_length", len(content))
        mlflow.log_metric("summarization.summary_length", len(response))

        return response
