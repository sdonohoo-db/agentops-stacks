"""FastAPI + FastMCP application setup."""

from fastapi import FastAPI, Request
from fastmcp import FastMCP

from .tools import health, register_tools
from .utils import header_store

mcp_server = FastMCP(name="custom-mcp-server")

register_tools(mcp_server)

mcp_app = mcp_server.http_app()

app = FastAPI(
    title="Custom MCP Server",
    version="0.1.0",
    lifespan=mcp_app.lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Example: a test route that exercises a registered tool.
# This calls the health() function directly — same code that runs
# when an MCP client calls the "health" tool. Use this pattern to
# add admin, debug, or integration test endpoints alongside your
# MCP tools.
@app.get("/test")
async def test_mcp():
    return {"status": "ok", "tool": "health", "result": health()}


combined_app = FastAPI(
    title="Combined MCP App",
    routes=[
        *mcp_app.routes,
        *app.routes,
    ],
    lifespan=mcp_app.lifespan,
)


@combined_app.middleware("http")
async def capture_headers(request: Request, call_next):
    header_store.set(dict(request.headers))
    return await call_next(request)
