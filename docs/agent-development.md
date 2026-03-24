---
title: Agent Development
description: Build, register, and wire agents using AgentBase, AgentRouter, and the Unity Catalog tool registry
category: development
tags: [agents, agentbase, router, tools, langchain, mlflow, tracing]
related_docs: [data-preparation.md, evaluation.md, deployment.md, extension-guide.md]
---

# Agent Development

All agents in the AgentOps framework extend `AgentBase` and are wired together via `AgentRouter`. This guarantees every agent is MLflow-traceable, UC-registerable, and swappable without changing client code.

---

## AgentBase

`framework/agent_development/agent_base.py`

Every agent inherits `AgentBase(mlflow.pyfunc.PythonModel)`. Subclasses implement one method: `_invoke()`.

```python
from framework.agent_development.agent_base import AgentBase

class MyAgent(AgentBase):
    def __init__(self):
        super().__init__(
            name="my_agent",
            description="Answers questions about internal policies",
        )

    def _invoke(self, messages, context=None) -> str:
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        # Your logic here — call an LLM, retriever, tools, etc.
        return "This is the response."
```

### What the base class provides

| Feature | How |
|---|---|
| MLflow tracing | `predict()` is decorated with `@mlflow.trace` |
| Standard interface | `predict(context, model_input)` compatible with `mlflow.pyfunc` |
| UC registration | `save()` logs to MLflow + registers with `@champion` alias |
| Input validation | `predict()` validates `messages` list before calling `_invoke()` |

### `predict()` input format

```python
model_input = {
    "messages": [
        {"role": "user", "content": "What is the refund policy?"},
        # optionally: {"role": "assistant", "content": "..."}
    ]
}
result = agent.predict(context=None, model_input=model_input)
# result: {"role": "assistant", "content": "..."}
```

### Saving and registering

```python
agent = MyAgent()
model_info = agent.save(
    artifact_path="my_agent",
    registered_model_name="agentops_dev.agentops.my_agent",
)
# Sets @champion alias automatically
```

---

## Building a RAG Agent

The reference implementation is in `reference_agent/agents/agent1/agent.py`.

```python
from langchain_databricks import ChatDatabricks, DatabricksVectorSearch
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from framework.agent_development.agent_base import AgentBase
from framework.config import get_config

RAG_PROMPT = ChatPromptTemplate.from_template("""
You are a helpful assistant. Use the retrieved context to answer the question.
If the context does not contain enough information, say so.

Context:
{context}

Question: {question}

Answer:""")


class RAGAgent(AgentBase):
    def __init__(self, config=None):
        cfg = config or get_config()
        super().__init__(name="rag_agent", description="Answers questions using RAG")
        self._cfg = cfg
        self._chain = None

    @property
    def chain(self):
        if self._chain is None:
            retriever = DatabricksVectorSearch(
                endpoint=self._cfg.vector_search_endpoint,
                index_name=self._cfg.vector_search_index_name,
                columns=["content", "source"],
            ).as_retriever(search_kwargs={"k": 5})

            llm = ChatDatabricks(
                endpoint=self._cfg.llm_endpoint,
                temperature=0.1,
                max_tokens=1024,
            )

            self._chain = (
                {"context": retriever, "question": RunnablePassthrough()}
                | RAG_PROMPT
                | llm
                | StrOutputParser()
            )
        return self._chain

    def _invoke(self, messages, context=None):
        question = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        return self.chain.invoke(question)
```

---

## Building a Summarization Agent

Reference: `reference_agent/agents/agent2/agent.py`.

```python
from langchain_databricks import ChatDatabricks
from langchain_core.prompts import ChatPromptTemplate

from framework.agent_development.agent_base import AgentBase
from framework.config import get_config

class SummarizationAgent(AgentBase):
    def __init__(self, config=None):
        cfg = config or get_config()
        super().__init__(name="summarization_agent", description="Summarizes documents")
        self._llm = ChatDatabricks(endpoint=cfg.llm_endpoint, temperature=0.0)

    def _invoke(self, messages, context=None):
        content = "\n".join(
            m["content"] for m in messages if m["role"] == "user"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Summarize the following content concisely."),
            ("human", "{content}"),
        ])
        chain = prompt | self._llm
        result = chain.invoke({"content": content})
        return result.content
```

---

## AgentRouter

`framework/agent_development/router.py`

The router is the single entry point for multi-agent applications. Register agents, then route.

```python
from framework.agent_development.router import AgentRouter

router = AgentRouter()

router.register_agent(
    name="qa",
    agent=RAGAgent(),
    description="Answers factual questions by retrieving from the knowledge base",
    keywords=["what", "how", "explain", "tell me", "describe"],
)
router.register_agent(
    name="summarize",
    agent=SummarizationAgent(),
    description="Summarizes long documents or conversation history",
    keywords=["summarize", "summary", "tldr", "overview", "condense"],
)

result = router.predict(None, {"messages": [{"role": "user", "content": "What is the policy?"}]})
```

### Routing logic

1. **Keyword fast path**: If any registered keyword appears in the message, route immediately.
2. **LLM classification**: If no keywords match, call the router LLM (`ChatDatabricks` with `max_tokens=20`) to classify intent.
3. **Default fallback**: If classification is ambiguous, route to the first registered agent.

### Building the reference router

```python
from reference_agent.router.router import build_router

router = build_router()  # Pre-wired with RAGAgent + SummarizationAgent
```

---

## Tool Registry

`framework/agent_development/tool_registry.py`

Register Python functions as Unity Catalog tools that agents can invoke.

```python
from framework.agent_development.tool_registry import ToolRegistry

registry = ToolRegistry(catalog="agentops_dev", schema="agentops")

@registry.register(
    name="lookup_document_metadata",
    description="Look up metadata for a source document by ID",
    parameters={
        "doc_id": {"type": "string", "description": "Document identifier"},
    },
)
def lookup_document_metadata(doc_id: str) -> dict:
    # Implementation
    return {"title": "...", "author": "...", "date": "..."}

registry.deploy()  # Creates UC functions via databricks-sdk
```

Reference tool implementations: `reference_agent/agents/agent1/tools.py`, `reference_agent/agents/agent2/tools.py`.

---

## MLflow Tracing

Every `predict()` call produces an MLflow trace automatically. Add spans inside `_invoke()` for finer-grained observability:

```python
import mlflow

def _invoke(self, messages, context=None):
    with mlflow.start_span(name="retrieval", span_type="RETRIEVER") as span:
        docs = self.retriever.invoke(question)
        span.set_attribute("num_docs", len(docs))

    with mlflow.start_span(name="generation", span_type="LLM") as span:
        response = self.llm.invoke(prompt)
        span.set_attribute("model", self._cfg.llm_endpoint)

    return response.content
```

Enable LangChain autologging (logs every LangChain call automatically). Call it **once in `__init__`**, before building the chain — not in `_invoke()`:

```python
import mlflow

class MyAgent(AgentBase):
    def __init__(self, config=None):
        super().__init__(name="my_agent", description="...")
        # Enable autologging once at construction time.
        # Calling it per-request in _invoke() causes redundant registrations.
        mlflow.langchain.autolog(log_traces=True, disable=False)
        self._chain = self._build_chain()
```

If your agent logs parameters in `__init__` (e.g., `mlflow.log_param()`), guard these calls because `__init__` also runs during Model Serving where no active run exists:

```python
if mlflow.active_run():
    mlflow.log_param("agent_name", self.name)
```

---

## Agent Development Workflow (DAB)

Defined in `bundle/resources/agent_development_workflow.yml`. Seven tasks:

```
router_dev
    ├── agent1_tools
    │       └── agent1_dev
    │               └── agent1_eval
    └── agent2_tools
            └── agent2_dev
                    └── agent2_eval
```

Each `*_dev` task registers the agent's UC tools, trains/configures the agent, and logs it to MLflow. Each `*_eval` task runs `reference_agent/eval/run_eval.py` and fails if thresholds are not met.

---

## Scaffolding a New Agent

```bash
python scripts/scaffold.py \
    --name customer_support \
    --description "Handles customer support queries using product docs" \
    --type rag
```

Creates:
- `reference_agent/agents/customer_support/agent.py`
- `reference_agent/agents/customer_support/tools.py`
- `reference_agent/eval/customer_support_eval_dataset.jsonl`
- `bundle/resources/customer_support_workflow.yml` (appended to)

Then:
1. Implement `_invoke()` in `agent.py`
2. Add eval samples to the JSONL file
3. Register in `reference_agent/router/router.py`

See [Extension Guide](extension-guide.md) for the full walkthrough.
