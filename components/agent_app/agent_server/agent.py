"""Minimal agent scaffold — edit this file to add your agent logic.

Define agent logic as standalone async functions, then register them with
invoke() and stream(). Keeping the logic separate means it's callable
from custom routes — see the /test route in start_server.py.
"""

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


async def handle_stream(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Stream a response. Replace this with your agent logic."""
    item_id = "msg_001"
    text = f"Agent scaffold is running. Current time: {datetime.now().isoformat()}"
    yield create_text_delta(text, item_id)


async def handle_invoke(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Handle a single request. Replace this with your agent logic."""
    outputs = [
        event.item
        async for event in handle_stream(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs)


# Register handlers with the AgentServer.
# To add a new tool or handler, define an async function above
# and register it here.
invoke()(handle_invoke)
stream()(handle_stream)
