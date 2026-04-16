"""MCP tool definitions.

Define tools as standalone functions, then register them in register_tools().
Keeping them as regular functions means they're importable and testable
outside the MCP protocol — see the /test route in app.py for an example.
"""

from server import utils


def health() -> dict:
    """Check MCP server health and Databricks connectivity."""
    return {
        "status": "healthy",
        "message": "MCP Server is running and connected to Databricks Apps.",
    }


def get_current_user() -> dict:
    """Get the current authenticated user's identity."""
    try:
        w = utils.get_user_authenticated_workspace_client()
        user = w.current_user.me()
        return {
            "display_name": user.display_name,
            "user_name": user.user_name,
            "active": user.active,
        }
    except Exception as e:
        return {"error": str(e), "message": "Failed to retrieve user information"}


def register_tools(mcp_server):
    """Register all tools with the MCP server.

    Each function above becomes an MCP tool that clients can call.
    Add new tools by defining a function and registering it here.
    """
    mcp_server.tool(health)
    mcp_server.tool(get_current_user)

    # To add a new tool:
    #
    # def my_tool(param: str) -> dict:
    #     """Description of what the tool does."""
    #     return {"result": f"Processed {param}"}
    #
    # mcp_server.tool(my_tool)
