"""
Unit Tests: Agent Router
Tests router dispatch logic without requiring LLM calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from framework.agent_development.router import AgentRouter
from framework.config import AgentOpsConfig


def make_config():
    return AgentOpsConfig(env="dev", llm_endpoint="test-endpoint")


def make_mock_agent(name: str, response: str = "test response"):
    agent = MagicMock()
    agent.predict.return_value = {"role": "assistant", "content": response}
    agent.name = name
    return agent


class TestAgentRouterKeywordMatching:
    def setup_method(self):
        self.config = make_config()
        self.router = AgentRouter(config=self.config)
        self.agent1 = make_mock_agent("qa", "Q&A response")
        self.agent2 = make_mock_agent("summarize", "Summary response")

        self.router.register_agent(
            name="qa",
            agent=self.agent1,
            description="Handles questions",
            keywords=["what", "how", "explain"],
        )
        self.router.register_agent(
            name="summarize",
            agent=self.agent2,
            description="Summarizes content",
            keywords=["summarize", "summary", "tldr"],
        )

    def test_keyword_routes_to_qa(self):
        result = self.router._classify_intent("What is the refund policy?")
        assert result == "qa"

    def test_keyword_routes_to_summarize(self):
        result = self.router._classify_intent("Summarize this document for me")
        assert result == "summarize"

    def test_keyword_case_insensitive(self):
        result = self.router._classify_intent("SUMMARIZE this please")
        assert result == "summarize"

    def test_no_keyword_defaults_to_first_agent(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="unknown")
        self.router._llm = mock_llm
        result = self.router._classify_intent("random unclassifiable input xyz")
        # Should default to first registered agent
        assert result == "qa"

    def test_register_agent_stores_correctly(self):
        assert "qa" in self.router._registered_agents
        assert "summarize" in self.router._registered_agents
        assert self.router._registered_agents["qa"]["description"] == "Handles questions"

    def test_no_agents_raises_on_classify(self):
        empty_router = AgentRouter(config=self.config)
        empty_router._llm = MagicMock()
        with pytest.raises((ValueError, Exception)):
            empty_router._classify_intent("test")

    def test_invoke_calls_correct_agent(self):
        messages = [{"role": "user", "content": "What is the policy?"}]
        self.router._invoke(messages)
        self.agent1.predict.assert_called_once()
        self.agent2.predict.assert_not_called()

    def test_invoke_empty_messages_returns_message(self):
        result = self.router._invoke([])
        assert "message" in result.lower() or len(result) > 0

    def test_invoke_no_user_messages_returns_message(self):
        messages = [{"role": "assistant", "content": "I am an assistant"}]
        result = self.router._invoke(messages)
        assert isinstance(result, str)
