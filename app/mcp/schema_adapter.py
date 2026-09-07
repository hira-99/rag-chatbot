"""Translate MCP tool schemas into the app's tool schema format, and
namespace them so a native tool and an MCP tool can never collide
(e.g. "bytemage_server__search_knowledge_base" vs the native
"search_knowledge_base").

"__" not "." -- OpenAI's tool-calling API requires function names to match
^[a-zA-Z0-9_-]+$, which a dot violates (confirmed live: a "." name gets
rejected with a 400 before the model ever sees the tool list).
"""

NAMESPACE_SEPARATOR = "__"


def namespaced_name(server_name, tool_name):
    return f"{server_name}{NAMESPACE_SEPARATOR}{tool_name}"


def mcp_tool_to_openai_schema(server_name, mcp_tool):
    return {
        "type": "function",
        "function": {
            "name": namespaced_name(server_name, mcp_tool.name),
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }
