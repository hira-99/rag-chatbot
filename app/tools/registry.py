"""Tool registry: function, input schema, risk level, description.

risk_level "safe" tools execute immediately; "requires_approval" tools stop
the agent loop and wait for a real UI action (app/tools/approvals.py,
Step 20) before running.
"""
from app.tools.native.calculator import CalculatorInput, calculate
from app.tools.native.customer import CustomerLookupInput, lookup_customer
from app.tools.native.knowledge import KnowledgeSearchInput, search_knowledge_base
from app.tools.native.time import TimeInput, get_current_time
from app.tools.schemas import build_tool_schema

TOOL_REGISTRY = {
    "calculate": {
        "function": calculate,
        "input_model": CalculatorInput,
        "description": "Evaluate an arithmetic expression, e.g. '12 * (4 + 3)'.",
        "risk_level": "safe",
    },
    "search_knowledge_base": {
        "function": search_knowledge_base,
        "input_model": KnowledgeSearchInput,
        "description": "Search ByteMage's internal documents (policies, handbook, roadmap) for information.",
        "risk_level": "safe",
    },
    "get_current_time": {
        "function": get_current_time,
        "input_model": TimeInput,
        "description": "Get the current UTC date and time.",
        "risk_level": "safe",
    },
    "lookup_customer": {
        "function": lookup_customer,
        "input_model": CustomerLookupInput,
        "description": "Look up a ByteMage customer's account by customer ID (e.g. 'CUST-1002'). Returns personal account data.",
        "risk_level": "requires_approval",
    },
}


def get_openai_tool_schemas(user_id):
    from app.mcp.registry import discover_mcp_tool_schemas
    from app.tools.permissions import allowed_tool_names

    native_schemas = [
        build_tool_schema(name, entry["description"], entry["input_model"])
        for name, entry in TOOL_REGISTRY.items()
        if name in allowed_tool_names(user_id)
    ]
    return native_schemas + discover_mcp_tool_schemas()


def requires_approval(tool_name):
    from app.mcp.registry import is_mcp_tool

    if is_mcp_tool(tool_name):
        # An MCP tool comes from an external server -- the host trusts its
        # own permission logic and approval gate, nothing else
        # automatically (Step 24's trust-boundary lesson), so every MCP
        # call is confirmed by a human regardless of what the server itself
        # claims about the tool.
        return True

    entry = TOOL_REGISTRY.get(tool_name)
    return bool(entry and entry["risk_level"] == "requires_approval")
