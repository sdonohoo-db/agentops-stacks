"""
RAG Agent (Agent 1)
===================
Retrieval-Augmented Generation agent that answers factual questions
by retrieving relevant context from the knowledge base vector search
index and generating responses using the Databricks Foundation Model API.

Architecture:
    User Query → Vector Search Retrieval → [Reranking] → Context Assembly → LLM → Response
                                                                            ↑
                                                                    MLflow Tracing

All LLM calls and retrieval operations are automatically traced via
mlflow.langchain.autolog() and the @mlflow.trace decorator on predict().

MLflow tracing captures:
  - Input messages
  - Retrieved chunks (retrieval span)
  - LLM call (LLM span with tokens, latency)
  - Final response

Retrieval modes:
  - ANN (default): pure semantic vector similarity search
  - Hybrid: semantic + keyword (BM25) combined — better recall for proper nouns
  - Hybrid + reranking: hybrid search over a larger candidate set, then
    re-scored with DatabricksReranker to maximize precision before the LLM

Example:
    >>> agent = RAGAgent()
    >>> result = agent.predict(None, {
    ...     "messages": [{"role": "user", "content": "What is the refund policy?"}]
    ... })
    >>> print(result["content"])

    >>> # Hybrid search + native Databricks reranker
    >>> agent = RAGAgent(query_type="hybrid", enable_reranking=True)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import mlflow
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_databricks import ChatDatabricks
from langchain_databricks.vectorstores import DatabricksVectorSearch
from pydantic import Field

from framework.agent_development.agent_base import AgentBase
from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


class _RerankingRetriever(BaseRetriever):
    """
    LangChain retriever that wraps the native Databricks Vector Search SDK
    and passes DatabricksReranker at query time.

    Uses the SDK directly (not the LangChain wrapper) because
    DatabricksReranker is a parameter on the underlying
    VectorSearchIndex.similarity_search() method.
    """

    endpoint: str = Field(...)
    index_name: str = Field(...)
    k: int = Field(default=5)
    num_candidates: int = Field(default=20)
    query_type: str = Field(default="hybrid")
    columns_to_rerank: List[str] = Field(default_factory=lambda: ["content"])
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager=None,
    ) -> List[Document]:
        from databricks.vector_search.client import VectorSearchClient
        from databricks.vector_search.index import DatabricksReranker

        vs_client = VectorSearchClient()
        index = vs_client.get_index(
            endpoint_name=self.endpoint,
            index_name=self.index_name,
        )

        kwargs: Dict[str, Any] = {
            "query_text": query,
            "columns": self.columns_to_rerank + ["doc_id", "chunk_id"],
            "num_results": self.num_candidates,
            "query_type": self.query_type,
            "reranker": DatabricksReranker(
                columns_to_rerank=self.columns_to_rerank,
            ),
        }
        if self.metadata_filter:
            kwargs["filters_json"] = self.metadata_filter

        raw = index.similarity_search(**kwargs)
        rows = raw.get("result", {}).get("data_array", [])
        col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]

        docs: List[Document] = []
        for row in rows[: self.k]:
            row_dict = dict(zip(col_names, row))
            content = row_dict.get("content", "")
            metadata = {k: v for k, v in row_dict.items() if k != "content"}
            docs.append(Document(page_content=content, metadata=metadata))

        return docs


RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

Context from the knowledge base:
{context}

Instructions:
- Base your answer primarily on the context provided above
- If the context doesn't fully answer the question, say what you can from the context and acknowledge the gap
- Be concise and accurate
- Cite which part of the context supports your answer when relevant"""

RAG_HUMAN_PROMPT = "{question}"


class RAGAgent(AgentBase):
    """
    Retrieval-Augmented Generation agent for factual Q&A.

    Retrieves relevant document chunks from the Vector Search index,
    assembles them as context, and generates a grounded response using
    the Databricks Foundation Model API.

    Supports hybrid search (keyword + semantic) and metadata filtering
    for more precise retrieval.

    This is Agent 1 in the reference multi-agent application.

    Example:
        >>> agent = RAGAgent()
        >>> result = agent.predict(None, {
        ...     "messages": [{"role": "user", "content": "What are the key benefits?"}]
        ... })
        >>> print(result["content"])

        >>> # With metadata filter
        >>> agent = RAGAgent(
        ...     query_type="hybrid",
        ...     metadata_filter={"category": {"LIKE": "policy%"}},
        ... )
    """

    def __init__(
        self,
        num_retrieved_chunks: int = 5,
        llm_endpoint: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        query_type: str = "ann",
        metadata_filter: Optional[Dict[str, Any]] = None,
        enable_reranking: bool = False,
        reranker_candidates: int = 20,
        columns_to_rerank: Optional[List[str]] = None,
    ) -> None:
        """
        Args:
            num_retrieved_chunks: Number of chunks returned to the LLM.
            llm_endpoint:         Override LLM endpoint name.
            config:               AgentOpsConfig (uses get_config() if None).
            query_type:           "ann" (semantic only) or "hybrid"
                                  (semantic + keyword BM25). Hybrid improves
                                  recall for exact-match queries and proper nouns.
            metadata_filter:      Optional filter applied at retrieval time.
                                  Uses Databricks Vector Search filter syntax:
                                  {"column": {"op": value}} — e.g.,
                                  {"category": {"LIKE": "policy%"}} or
                                  {"doc_id": {"IN": ["id1", "id2"]}}.
                                  Pass at init for a static filter, or override
                                  per-call via _invoke()'s filter_overrides param.
            enable_reranking:     If True, use DatabricksReranker to re-score
                                  retrieved chunks before passing to the LLM.
                                  Improves precision at the cost of one extra
                                  SDK call. Combines well with query_type="hybrid".
            reranker_candidates:  Number of candidates to retrieve before reranking.
                                  Only used when enable_reranking=True. Should be
                                  larger than num_retrieved_chunks (default 20).
                                  The reranker selects the top num_retrieved_chunks
                                  from this candidate set.
            columns_to_rerank:    Columns passed to DatabricksReranker for scoring.
                                  Defaults to ["content"]. Include summary or
                                  other text columns if they are in your index.
        """
        super().__init__(
            name="rag_agent",
            description="Answers factual questions using retrieval-augmented generation",
            config=config,
        )
        self.num_retrieved_chunks = num_retrieved_chunks
        self._llm_endpoint = llm_endpoint or self.config.llm_endpoint
        self.query_type = query_type
        self.metadata_filter = metadata_filter
        self.enable_reranking = enable_reranking
        self.reranker_candidates = max(reranker_candidates, num_retrieved_chunks)
        self.columns_to_rerank = columns_to_rerank or ["content"]
        self._retriever = None
        self._llm = None
        # Enable autologging once at construction time (not per-invocation)
        mlflow.langchain.autolog(log_traces=True, disable=False)

    def _build_retriever(self, filter_overrides: Optional[Dict[str, Any]] = None):
        """
        Build the Vector Search retriever.

        When enable_reranking=True, returns a _RerankingRetriever that calls
        the native VS SDK with DatabricksReranker. Otherwise uses the standard
        LangChain DatabricksVectorSearch wrapper.
        """
        active_filter = filter_overrides or self.metadata_filter

        if self.enable_reranking:
            return _RerankingRetriever(
                endpoint=self.config.vector_search_endpoint,
                index_name=self.config.vector_search_index_name,
                k=self.num_retrieved_chunks,
                num_candidates=self.reranker_candidates,
                query_type=self.query_type,
                columns_to_rerank=self.columns_to_rerank,
                metadata_filter=active_filter,
            )

        search_kwargs: Dict[str, Any] = {"k": self.num_retrieved_chunks}
        if self.query_type == "hybrid":
            search_kwargs["query_type"] = "hybrid"
        if active_filter:
            search_kwargs["filters"] = active_filter

        vs = DatabricksVectorSearch(
            endpoint=self.config.vector_search_endpoint,
            index_name=self.config.vector_search_index_name,
            text_column="content",
        )
        return vs.as_retriever(search_kwargs=search_kwargs)

    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = self._build_retriever()
        return self._retriever

    @property
    def llm(self):
        if self._llm is None:
            self._llm = ChatDatabricks(
                endpoint=self._llm_endpoint,
                temperature=0.1,
                max_tokens=1024,
            )
        return self._llm

    def _build_chain(self, filter_overrides: Optional[Dict[str, Any]] = None):
        """Build the LangChain RAG chain."""
        retriever = self._build_retriever(filter_overrides)

        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("human", RAG_HUMAN_PROMPT),
        ])

        def format_docs(docs) -> str:
            return "\n\n---\n\n".join(
                f"[Source: {doc.metadata.get('doc_id', 'unknown')}]\n{doc.page_content}"
                for doc in docs
            )

        return (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )

    @mlflow.trace(name="rag_agent.invoke", span_type="AGENT")
    def _invoke(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Any] = None,
        filter_overrides: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Retrieve context and generate a grounded response.

        Traces the full execution with MLflow:
          - Retrieval span: which chunks were fetched and filter applied
          - LLM span: token usage and latency

        Args:
            messages:        Conversation messages list.
            context:         MLflow pyfunc context (unused, passed by base class).
            filter_overrides: Per-call metadata filter that overrides the
                              instance-level metadata_filter. Useful when the
                              router knows the document category from routing logic.
        """
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return "Please provide a question."

        question = user_messages[-1].get("content", "")

        with mlflow.start_span(name="retrieval", span_type="RETRIEVER") as span:
            span.set_inputs({
                "query": question,
                "query_type": self.query_type,
                "num_chunks": self.num_retrieved_chunks,
                "reranking_enabled": self.enable_reranking,
                "reranker_candidates": self.reranker_candidates if self.enable_reranking else None,
                "filter": filter_overrides or self.metadata_filter,
            })
            chain = self._build_chain(filter_overrides)
            response = chain.invoke(question)
            span.set_outputs({"response_length": len(response)})

        return response
