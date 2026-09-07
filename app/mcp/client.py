"""MCP client session management -- connects to allowlisted servers
(app/mcp/security.py) and exposes sync list_tools/call_tool, bridging the
SDK's async API (app/mcp/connection.py) for the rest of this sync app.
"""
from app.mcp.connection import MCPConnection
from app.mcp.security import ALLOWED_SERVERS

_connections = {}


def connect(server_name):
    if server_name in _connections:
        return _connections[server_name]

    config = ALLOWED_SERVERS.get(server_name)
    if config is None:
        raise ValueError(f"'{server_name}' is not an allowlisted MCP server")

    connection = MCPConnection(config["command"], config["args"])
    if not connection.start():
        return None

    _connections[server_name] = connection
    return connection


async def _list_tools(session):
    result = await session.list_tools()
    return result.tools


async def _call_tool(session, tool_name, arguments):
    return await session.call_tool(tool_name, arguments)


def list_tools(server_name):
    connection = connect(server_name)
    if connection is None:
        return []
    return connection.call(_list_tools)


def call_tool(server_name, tool_name, arguments):
    connection = connect(server_name)
    if connection is None:
        return {"error": f"MCP server '{server_name}' is unavailable"}

    result = connection.call(_call_tool, tool_name, arguments)
    text_parts = [block.text for block in result.content if hasattr(block, "text")]
    return {"text": "\n".join(text_parts)}
