"""Runs the agent test cases (app/evaluation/datasets.py) against the
real routing/tool-calling code (Section E): checks route selection, tool
selection, and forbidden-tool avoidance (Step 26.2, 26.6).
"""
from app.agent.loop import run_agent
from app.agent.policies import route_turn
from app.config import DEFAULT_USER_ID
from app.evaluation.datasets import AGENT_TEST_CASES
from app.llm.messages import assemble_context
from app.mcp.schema_adapter import NAMESPACE_SEPARATOR


def _base_tool_name(tool_name):
    """An MCP-namespaced tool ("bytemage_server__calculate") and its
    native equivalent ("calculate") should count as the same selection for
    evaluation purposes -- which one the model picks is a real behavior
    worth noting, but not a tool-selection failure either way."""
    return tool_name.split(NAMESPACE_SEPARATOR, 1)[-1]


def run_agent_evaluation(test_cases=AGENT_TEST_CASES):
    results = []
    for case in test_cases:
        route, _ = route_turn(case.message)
        route_correct = route == case.expected_route

        tools_used = []
        if route == "agentic":
            messages = assemble_context([{"role": "user", "content": case.message}])
            for event in run_agent(messages, DEFAULT_USER_ID, run_id=f"eval-{case.case_id}"):
                # A tool the model selects but that then needs approval
                # never reaches a "tool_call" event (the loop stops at
                # "awaiting_approval" before executing it) -- selection is
                # what this checks, not execution, so credit it here too.
                if event["status"] == "tool_call":
                    tools_used.append(_base_tool_name(event["tool_name"]))
                elif event["status"] == "awaiting_approval":
                    tools_used.append(_base_tool_name(event["pending_tool_call"]["name"]))
                if event["status"] in ("done", "awaiting_approval"):
                    break

        missing_tools = [t for t in case.expected_tool_names if t not in tools_used]
        forbidden_used = [t for t in tools_used if t in case.forbidden_tool_names]

        results.append({
            "case_id": case.case_id,
            "message": case.message,
            "route_correct": route_correct,
            "tools_used": tools_used,
            "missing_expected_tools": missing_tools,
            "forbidden_tools_used": forbidden_used,
            "passed": route_correct and not missing_tools and not forbidden_used,
        })

    pass_rate = sum(1 for r in results if r["passed"]) / len(results) if results else 0.0
    return {"cases": results, "pass_rate": pass_rate}
