"""Namespaced registry of discovered MCP tools -- merged into the same
tool set the agent loop calls through (app/tools/registry.py), so the
loop doesn't need to distinguish native tools from MCP tools.
"""
from app.mcp.client import call_tool, list_tools
from app.mcp.schema_adapter import NAMESPACE_SEPARATOR, mcp_tool_to_openai_schema
from app.mcp.security import ALLOWED_SERVERS

_discovered_schemas = None


def discover_mcp_tool_schemas():
    """Connects to every allowlisted server and returns their tools as
    OpenAI-format schemas, already namespaced. Cached after the first
    call -- a server's tool list doesn't change mid-session, and
    reconnecting on every model call would be wasteful. A server that
    fails to connect just contributes no tools (Step 24's item 10) rather
    than breaking the rest of the assistant.
    """
    global _discovered_schemas
    if _discovered_schemas is not None:
        return _discovered_schemas

    schemas = []
    for server_name in ALLOWED_SERVERS:
        try:
            for tool in list_tools(server_name):
                schemas.append(mcp_tool_to_openai_schema(server_name, tool))
        except Exception as exc:
            print(f"[mcp] '{server_name}' unavailable: {exc}")
    _discovered_schemas = schemas
    return schemas


def is_mcp_tool(tool_name):
    return NAMESPACE_SEPARATOR in tool_name and tool_name.split(NAMESPACE_SEPARATOR, 1)[0] in ALLOWED_SERVERS


def execute_mcp_tool(namespaced_tool_name, arguments):
    server_name, real_tool_name = namespaced_tool_name.split(NAMESPACE_SEPARATOR, 1)
    return call_tool(server_name, real_tool_name, arguments)
