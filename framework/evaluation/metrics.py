"""
Custom Evaluation Metrics
=========================
Domain-specific scorer metrics for AgentOps evaluation, built on top
of mlflow.genai.scorers.Guidelines.

Use these alongside the standard scorers (Correctness, RetrievalGroundedness,
RelevanceToQuery, Safety) for domain-specific quality signals.

Reference:
    https://mlflow.org/docs/latest/llms/llm-evaluate/index.html#custom-llm-as-judge-metrics
"""

from __future__ import annotations

import logging

from mlflow.genai.scorers import (
    Correctness,
    Guidelines,
    RelevanceToQuery,
    RetrievalGroundedness,
    Safety,
)

logger = logging.getLogger(__name__)


def citation_accuracy_scorer() -> Guidelines:
    """
    Scorer: checks that the agent cites sources accurately when using retrieved context.

    Particularly important for RAG agents — checks that quoted text
    actually appears in the retrieved context.

    Returns:
        mlflow.genai.scorers.Guidelines instance.

    Example:
        >>> from framework.evaluation.metrics import citation_accuracy_scorer
        >>> from framework.evaluation.evaluator import AgentEvaluator
        >>> evaluator = AgentEvaluator(agent_name="rag_agent")
        >>> result = evaluator.run(agent, data, extra_scorers=[citation_accuracy_scorer()])
    """
    return Guidelines(
        name="citation_accuracy",
        guidelines=(
            "Evaluate whether the response accurately cites or references information "
            "from the retrieved context. The response should not fabricate citations "
            "or attribute information to sources that don't support the claim. "
            "Score 'yes' if all claims are traceable to the provided context or are "
            "general knowledge. Score 'no' if the response invents citations or "
            "misattributes claims to documents not present in the context."
        ),
    )


def response_completeness_scorer() -> Guidelines:
    """
    Scorer: checks whether the response fully addresses all parts of the user's question.

    Catches agents that answer part of a multi-part question but omit the rest.

    Returns:
        mlflow.genai.scorers.Guidelines instance.
    """
    return Guidelines(
        name="response_completeness",
        guidelines=(
            "Evaluate whether the response completely addresses the user's full question. "
            "If the question has multiple parts, all parts should be addressed. "
            "Score 'yes' if the response addresses all explicit aspects of the question. "
            "Score 'no' if the response ignores or partially skips parts of the question."
        ),
    )


def conciseness_scorer() -> Guidelines:
    """
    Scorer: checks whether the response is appropriately concise without omitting key info.

    Catches overly verbose responses that bury the answer in unnecessary detail.

    Returns:
        mlflow.genai.scorers.Guidelines instance.
    """
    return Guidelines(
        name="conciseness",
        guidelines=(
            "Evaluate whether the response is appropriately concise. A good response "
            "delivers the key information without unnecessary padding, repetition, or "
            "excessive caveats. Score 'yes' if the response is appropriately sized "
            "for the question — neither overly terse nor excessively verbose. "
            "Score 'no' if the response is padded with filler text, repeats itself, "
            "or includes large amounts of information irrelevant to the question."
        ),
    )


def professional_tone_scorer() -> Guidelines:
    """
    Scorer: checks whether the agent maintains an appropriate professional tone.

    Use for customer-facing agents where tone consistency matters.

    Returns:
        mlflow.genai.scorers.Guidelines instance.
    """
    return Guidelines(
        name="professional_tone",
        guidelines=(
            "Evaluate whether the response uses a professional, helpful, and respectful tone. "
            "Score 'yes' if the response is professional, clear, and appropriate "
            "for a business context. Score 'no' if the response is dismissive, "
            "condescending, overly casual, or uses inappropriate language."
        ),
    )


def get_standard_scorers() -> list:
    """
    Return the full standard scorer set for AgentOps evaluation.

    Combines mlflow.genai built-in scorers with AgentOps custom scorers.

    Returns:
        List of scorer objects ready for mlflow.genai.evaluate(scorers=...).

    Example:
        >>> import mlflow.genai
        >>> results = mlflow.genai.evaluate(
        ...     predict_fn=predict_fn,
        ...     data=eval_df,
        ...     scorers=get_standard_scorers(),
        ... )
    """
    return [
        Correctness(),
        RetrievalGroundedness(),
        RelevanceToQuery(),
        Safety(),
        citation_accuracy_scorer(),
        response_completeness_scorer(),
        conciseness_scorer(),
        professional_tone_scorer(),
    ]
