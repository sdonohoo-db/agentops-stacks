from pathlib import Path

from dotenv import load_dotenv
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import agent_server.agent  # noqa: E402, F401

agent_server = AgentServer("ResponsesAgent")

app = agent_server.app
setup_mlflow_git_based_version_tracking()


# Example: a test route that sends a sample request through the agent.
# The AgentServer's app is a regular FastAPI app — add routes to it
# for admin, debug, or integration test endpoints alongside your agent.
@app.get("/test")
async def test_agent():
    from agent_server.agent import handle_invoke
    from mlflow.types.responses import ResponsesAgentRequest

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "test"}],
    )
    response = await handle_invoke(request)
    return response


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")
