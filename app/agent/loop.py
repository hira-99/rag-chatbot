"""Observe-decide-act agent loop (Step 18): repeatedly send state to the
model, execute any tool calls it requests, and feed results back -- until
it answers with plain text, a tool needs approval, or MAX_STEPS is hit.

A generator, not a plain function: it yields between every model/tool
call so app/main.py's cancels= (A.6's mechanism) can interrupt a run
between steps, and so the UI can show tool-progress text as it happens.
"""
import json

from app.agent.limits import MAX_STEPS
from app.agent.state import AgentState
from app.config import MODEL_NAME
from app.llm.client import client
from app.observability.tracing import traced_span
from app.tools.executor import execute_tool
from app.tools.registry import get_openai_tool_schemas, requires_approval


def _assistant_message_with_tool_calls(choice):
    return {
        "role": "assistant",
        "content": choice.content,
        "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in choice.tool_calls
        ],
    }


def run_agent(messages, user_id, run_id, conversation_id=None, trace_id=None):
    """Yields progress dicts ({"status": "tool_call", ...}) and ends by
    yielding exactly one terminal dict: {"status": "done", "text", "messages"}
    or {"status": "awaiting_approval", "messages", "pending_tool_call"}.

    trace_id (Section H): when given, each executed tool call gets its own
    span nested under the turn's trace, alongside the retrieval/model_call
    spans app/ui/chat.py already logs. Optional -- callers outside the
    live chat turn (a resumed approval, a direct test) can omit it.
    """
    state = AgentState(run_id=run_id, conversation_id=conversation_id, user_id=user_id, messages=list(messages))
    tool_schemas = get_openai_tool_schemas(user_id)

    for state.step in range(MAX_STEPS):
        yield {"status": "thinking"}
        response = client.chat.completions.create(model=MODEL_NAME, messages=state.messages, tools=tool_schemas)
        choice = response.choices[0].message

        if not choice.tool_calls:
            state.status = "done"
            yield {"status": "done", "text": choice.content or "", "messages": state.messages}
            return

        state.messages.append(_assistant_message_with_tool_calls(choice))

        for tool_call in choice.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")
            signature = (tool_name, tool_call.function.arguments)

            if requires_approval(tool_name) and signature not in state.seen_tool_calls:
                state.status = "awaiting_approval"
                yield {
                    "status": "awaiting_approval",
                    "messages": state.messages,
                    "pending_tool_call": {"id": tool_call.id, "name": tool_name, "arguments": arguments},
                }
                return

            yield {"status": "tool_call", "tool_name": tool_name, "arguments": arguments}

            if signature in state.seen_tool_calls:
                # Repetition guard (Step 18): don't run the exact same call
                # a second time -- push the model to answer with what it has.
                result = {"error": "This exact tool call was already made this turn. Answer using the results already gathered."}
            elif trace_id:
                with traced_span(trace_id, trace_id, user_id, conversation_id, "tool_call", tool_name,
                                  input_data=arguments) as span:
                    state.seen_tool_calls.add(signature)
                    result = execute_tool(tool_name, arguments, user_id=user_id, run_id=run_id, conversation_id=conversation_id)
                    span["result_preview"] = str(result)[:300]
            else:
                state.seen_tool_calls.add(signature)
                result = execute_tool(tool_name, arguments, user_id=user_id, run_id=run_id, conversation_id=conversation_id)

            state.messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

    state.status = "done"
    yield {"status": "done", "text": "I've reached my step limit for this turn -- here's what I found so far.", "messages": state.messages}


def start_fixed_customer_lookup(customer_id, user_id, run_id, conversation_id):
    """The illustrative fixed workflow (E.5): a customer lookup by ID is
    deterministic enough that no model decision is needed to pick the tool
    or its arguments -- unlike run_agent, which lets the model decide what
    to call. The lookup itself still goes through the same approval gate,
    since it's the same sensitive tool either way.

    Returns (pending_tool_call, seed_messages) for the caller to hand to
    app/tools/approvals.request_approval -- seed_messages includes the
    fabricated assistant tool_calls message the API requires before a
    tool-role result can follow it.
    """
    call_id = f"fixed-{run_id}"
    pending_tool_call = {"id": call_id, "name": "lookup_customer", "arguments": {"customer_id": customer_id}}
    seed_messages = [
        {"role": "system", "content": "You are a helpful assistant for ByteMage. Answer using only the tool result provided."},
        {"role": "user", "content": f"Look up customer {customer_id} and summarize their account."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": "lookup_customer", "arguments": json.dumps({"customer_id": customer_id})},
            }],
        },
    ]
    return pending_tool_call, seed_messages


def resume_after_approval(messages, pending_tool_call, user_id, run_id, conversation_id, approved):
    """Runs after a human approves/rejects a pending tool call
    (app/tools/approvals.py) -- appends the tool's result (or a rejection
    notice) and re-enters the loop so the model can continue from there.
    """
    if approved:
        result = execute_tool(
            pending_tool_call["name"], pending_tool_call["arguments"],
            user_id=user_id, run_id=run_id, conversation_id=conversation_id,
        )
    else:
        result = {"error": "The user rejected this action. Do not attempt it again this turn."}

    resumed_messages = messages + [{"role": "tool", "tool_call_id": pending_tool_call["id"], "content": json.dumps(result)}]
    yield from run_agent(resumed_messages, user_id, run_id, conversation_id)
