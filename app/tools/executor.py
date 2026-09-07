"""Central tool executor: validate input, check permissions, execute
(reusing a prior result if idempotent), normalize and record the result.

This is the only code path that ever runs a tool -- native or MCP. The
model can only *request* a call; nothing it says makes that call happen.
"""
import json
import uuid

from app.database.connection import get_connection
from app.database.models import find_tool_call_by_idempotency_key, record_tool_call
from app.tools.idempotency import make_idempotency_key
from app.tools.permissions import allowed_tool_names
from app.tools.registry import TOOL_REGISTRY


def _run_and_record(tool_name, arguments, user_id, run_id, conversation_id, call_fn):
    """Shared idempotency + audit-trail wrapper for both native and MCP
    tool calls -- call_fn() actually runs the tool and returns its result."""
    key = make_idempotency_key(user_id, tool_name, arguments, run_id)
    conn = get_connection()
    existing = find_tool_call_by_idempotency_key(conn, key)
    if existing:
        conn.close()
        return json.loads(existing["result"])

    result = call_fn()

    record_tool_call(
        conn, uuid.uuid4().hex, run_id, conversation_id, user_id,
        tool_name, json.dumps(arguments), json.dumps(result), key,
    )
    conn.close()
    return result


def execute_tool(tool_name, arguments, user_id, run_id=None, conversation_id=None):
    from app.mcp.registry import execute_mcp_tool, is_mcp_tool

    if is_mcp_tool(tool_name):
        # MCP tool schemas come straight from the server (already
        # JSON-schema) -- no local Pydantic model to validate against, but
        # every call still goes through idempotency and the audit trail
        # like a native call. Every user is allowed the one allowlisted
        # server for now (single-user scope, same as permissions.py).
        return _run_and_record(
            tool_name, arguments, user_id, run_id, conversation_id,
            call_fn=lambda: execute_mcp_tool(tool_name, arguments),
        )

    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return {"error": f"Unknown tool: {tool_name}"}

    if tool_name not in allowed_tool_names(user_id):
        return {"error": f"You don't have permission to use '{tool_name}'."}

    try:
        validated = entry["input_model"](**arguments)
    except Exception as exc:
        return {"error": f"Invalid arguments for '{tool_name}': {exc}"}

    def call_native():
        try:
            return entry["function"](**validated.model_dump())
        except Exception as exc:
            return {"error": f"'{tool_name}' failed: {exc}"}

    return _run_and_record(tool_name, arguments, user_id, run_id, conversation_id, call_fn=call_native)
