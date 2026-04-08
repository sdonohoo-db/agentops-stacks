"""Minimal agent scaffold — replace with your agent logic."""

import logging
from datetime import datetime
from typing import AsyncGenerator

from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    create_text_delta,
)

logger = logging.getLogger(__name__)


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Handle a single request. Replace this with your agent logic."""
    outputs = [
        event.item
        async for event in stream_handler(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs)


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Stream a response. Replace this with your agent logic."""
    text = f"Agent scaffold is running. Current time: {datetime.now().isoformat()}"
    yield create_text_delta(text)
