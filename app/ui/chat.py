"""Gradio chat interface: token streaming, tool-progress events, cancellation."""
import uuid

import gradio as gr

from app.agent.loop import run_agent, start_fixed_customer_lookup
from app.agent.policies import route_turn
from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    add_message,
    get_conversation_summary,
    get_messages,
    get_or_create_conversation,
    mark_last_assistant_message_replaced,
    new_conversation_id,
    rename_conversation,
    save_message_feedback,
)
from app.llm.client import generate_title, stream_chat_completion
from app.llm.messages import assemble_context
from app.llm.token_counter import count_tokens
from app.memory.extraction import apply_saving_rules, extract_candidates
from app.memory.retrieval import retrieve_relevant_memories
from app.memory.short_term import split_recent_and_archived
from app.memory.storage import maybe_update_summary, save_extracted_memories
from app.observability.cost import check_within_limits
from app.observability.logging import new_trace_id
from app.observability.tracing import traced_span
from app.retrieval.citations import assign_source_numbers, format_sources_for_prompt, validate_citations
from app.retrieval.hybrid_search import retrieve_for_query
from app.tools.approvals import request_approval


def _as_text(content):
    """Gradio's Chatbot normalizes message content into a list of content
    parts (e.g. [{"type": "text", "text": "..."}]) once it round-trips
    through the frontend, rather than keeping the plain string we sent --
    confirmed live via the actual chatbot_history payload. Every place that
    reads chatbot_history as plain text needs this.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def user_submit(message, chatbot_history, conversation_id):
    """Runs first: persist the user's message (never partial, safe to save
    immediately) and echo it into the chat pane. Clears the textbox.

    conversation_id can be None on a brand new session (nothing clicked or
    typed yet) -- generate one on the fly rather than requiring the user to
    press "New Conversation" before they're allowed to type.
    """
    if not message.strip():
        return "", chatbot_history, conversation_id

    if not conversation_id:
        conversation_id = new_conversation_id()

    conn = get_connection()
    get_or_create_conversation(conn, conversation_id, DEFAULT_USER_ID, title="New conversation")
    add_message(conn, conversation_id, DEFAULT_USER_ID, "user", message, token_count=count_tokens(message))
    conn.close()

    return "", chatbot_history + [{"role": "user", "content": message}], conversation_id


def _persist_assistant_reply(conversation_id, recent_messages, text):
    conn = get_connection()
    add_message(conn, conversation_id, DEFAULT_USER_ID, "assistant", text, token_count=count_tokens(text))

    # First exchange in this conversation (1 user + 1 assistant message so far)?
    # Generate a real title instead of leaving it as "New conversation".
    if len(get_messages(conn, conversation_id)) == 2:
        title = generate_title(recent_messages[-1]["content"], text)
        rename_conversation(conn, conversation_id, title)

    conn.close()

    # Section F: fold any newly archived turns into the running summary,
    # and pull any durable facts out of this exchange for long-term memory.
    maybe_update_summary(conversation_id, recent_messages + [{"role": "assistant", "content": text}])
    candidates = apply_saving_rules(extract_candidates(recent_messages[-1]["content"], text))
    if candidates:
        save_extracted_memories(DEFAULT_USER_ID, candidates, conversation_id)


def _load_memory_context(conversation_id, recent_messages, latest_message):
    """Section F's two memory sources for this turn: the conversation's
    running summary (short-term, for anything already outside the sliding
    window) and any long-term memories relevant to the current message.
    Also returns the windowed recent-messages slice to actually send.
    """
    windowed_recent, _ = split_recent_and_archived(recent_messages)

    conn = get_connection()
    summary_row = get_conversation_summary(conn, conversation_id)
    conn.close()
    conversation_summary = summary_row["summary_text"] if summary_row else None

    relevant_memories = retrieve_relevant_memories(DEFAULT_USER_ID, latest_message)
    long_term_memories = [m["memory_text"] for m in relevant_memories] or None

    return windowed_recent, conversation_summary, long_term_memories


def _respond_plain(chatbot_history, recent_messages, conversation_id, trace_id):
    """The Section B/D path: retrieve if the router decides this turn needs
    documents, then stream the reply token by token."""
    latest_message = recent_messages[-1]["content"]
    windowed_recent, conversation_summary, long_term_memories = _load_memory_context(
        conversation_id, recent_messages, latest_message
    )

    with traced_span(trace_id, trace_id, DEFAULT_USER_ID, conversation_id, "retrieval", "retrieve_for_query",
                      input_data={"query": latest_message}) as span:
        retrieval_result = retrieve_for_query(latest_message, conversation_history=recent_messages[:-1])
        span["chunk_count"] = len(retrieval_result["chunks"])
        span["route"] = retrieval_result["route"]

    sources = assign_source_numbers(retrieval_result["chunks"]) if retrieval_result["chunks"] else []
    retrieved_evidence = [format_sources_for_prompt(sources)] if sources else None

    messages = assemble_context(
        windowed_recent, conversation_summary=conversation_summary,
        long_term_memories=long_term_memories, retrieved_evidence=retrieved_evidence,
    )

    chatbot_history = chatbot_history + [{"role": "assistant", "content": ""}]
    partial_response = ""
    with traced_span(trace_id, trace_id, DEFAULT_USER_ID, conversation_id, "model_call", "stream_chat_completion") as span:
        for delta in stream_chat_completion(messages):
            partial_response += delta
            chatbot_history[-1]["content"] = partial_response
            yield chatbot_history
        span["response_length"] = len(partial_response)

    if sources:
        citation_check = validate_citations(partial_response, sources)
        if citation_check["unknown_citations"]:
            print(f"[citations] unknown citation numbers in response: {citation_check['unknown_citations']}")

    _persist_assistant_reply(conversation_id, recent_messages, partial_response)


def _respond_agentic(chatbot_history, recent_messages, conversation_id, trace_id):
    """Section E's agent loop: the model decides which tool(s) to call and
    in what order. No retrieval here -- search_knowledge_base is available
    to the model as a tool if it decides it needs one."""
    run_id = uuid.uuid4().hex
    latest_message = recent_messages[-1]["content"]
    windowed_recent, conversation_summary, long_term_memories = _load_memory_context(
        conversation_id, recent_messages, latest_message
    )
    messages = assemble_context(
        windowed_recent, conversation_summary=conversation_summary, long_term_memories=long_term_memories
    )

    chatbot_history = chatbot_history + [{"role": "assistant", "content": "Thinking..."}]
    yield chatbot_history

    final_text = "Something went wrong before I could finish."
    for event in run_agent(messages, DEFAULT_USER_ID, run_id, conversation_id, trace_id=trace_id):
        if event["status"] == "tool_call":
            chatbot_history[-1]["content"] = f"🔧 Calling `{event['tool_name']}`..."
            yield chatbot_history
        elif event["status"] == "awaiting_approval":
            request_approval(run_id, conversation_id, DEFAULT_USER_ID, event["pending_tool_call"], event["messages"])
            call = event["pending_tool_call"]
            final_text = (
                f"This action needs your approval before I can continue: **{call['name']}**"
                f"({call['arguments']}). Check the Approvals panel to approve or reject."
            )
        elif event["status"] == "done":
            final_text = event["text"]

    chatbot_history[-1]["content"] = final_text
    yield chatbot_history

    _persist_assistant_reply(conversation_id, recent_messages, final_text)


def _respond_fixed_workflow(chatbot_history, recent_messages, conversation_id, customer_id, trace_id):
    """E.5's illustrative fixed workflow: a customer lookup by ID needs no
    model decision about which tool to call -- straight to the approval
    gate, contrasted with _respond_agentic's model-decided path."""
    run_id = uuid.uuid4().hex
    pending_tool_call, seed_messages = start_fixed_customer_lookup(customer_id, DEFAULT_USER_ID, run_id, conversation_id)
    request_approval(run_id, conversation_id, DEFAULT_USER_ID, pending_tool_call, seed_messages)

    final_text = (
        f"Looking up customer **{customer_id}** needs your approval since it returns personal "
        f"account data -- check the Approvals panel to approve or reject."
    )
    chatbot_history = chatbot_history + [{"role": "assistant", "content": final_text}]
    yield chatbot_history

    _persist_assistant_reply(conversation_id, recent_messages, final_text)


def bot_respond(chatbot_history, conversation_id):
    """Runs second (chained after user_submit): reply to the latest turn
    and persist it once finished, generating a title on the first exchange.

    Dispatches on app/agent/policies.route_turn: most turns are "plain"
    (Section B/D's streaming path); a turn that plainly needs a tool the
    router doesn't cover goes through the agent loop or, for the one
    deterministic case, the fixed workflow (Section E).
    """
    allowed, reason = check_within_limits(DEFAULT_USER_ID)
    if not allowed:
        yield chatbot_history + [{"role": "assistant", "content": f"⚠️ {reason}"}]
        return

    recent_messages = [{"role": m["role"], "content": _as_text(m["content"])} for m in chatbot_history]
    latest_message = recent_messages[-1]["content"]
    route, route_arg = route_turn(latest_message)

    # One trace per turn (Section H): the "turn" span here is the trace's
    # root (parent_span_id=None, what list_recent_traces finds); retrieval/
    # model_call/tool_call spans below reference trace_id as their parent --
    # a flat one-level nesting under the trace, not a true per-span parent
    # chain, but enough to reconstruct everything that happened in one turn.
    trace_id = new_trace_id()
    with traced_span(trace_id, None, DEFAULT_USER_ID, conversation_id, "turn", f"bot_respond:{route}",
                      input_data={"message": latest_message, "route": route}):
        if route == "fixed_workflow":
            yield from _respond_fixed_workflow(chatbot_history, recent_messages, conversation_id, route_arg, trace_id)
        elif route == "agentic":
            yield from _respond_agentic(chatbot_history, recent_messages, conversation_id, trace_id)
        else:
            yield from _respond_plain(chatbot_history, recent_messages, conversation_id, trace_id)


def regenerate_response(retry_data: gr.RetryData, chatbot_history, conversation_id):
    """Wired to Gradio Chatbot's native .retry() event (main.py) -- fires
    when the user clicks the retry icon under the last assistant reply.

    retry_data.index is the index of the USER message whose reply is being
    regenerated (confirmed by testing live -- Gradio's own docstring example
    is misleading about this). Truncating to that index keeps everything up
    to and including that user message, dropping the old reply.

    The old reply is marked replaced (is_active=0), not deleted -- the
    roadmap's "mark it replaced" option, chosen over full branching to keep
    this stage's scope manageable; the previous response is still in the
    database for audit, just not shown or sent to the model again.

    Regenerating an agentic/fixed-workflow turn gets a fresh run_id, so its
    tool calls are re-executed rather than reused via idempotency (E.4's
    idempotency keys are scoped to one run). Acceptable here because every
    registered tool is read-only (calculator, knowledge search, time,
    customer lookup) -- re-running one wastes a call but changes nothing.
    A tool with real side effects would need this to carry the original
    run_id forward instead.
    """
    conn = get_connection()
    mark_last_assistant_message_replaced(conn, conversation_id)
    conn.close()

    truncated_history = chatbot_history[: retry_data.index + 1]
    yield from bot_respond(truncated_history, conversation_id)


def do_feedback(conversation_id, reason, like_data: gr.LikeData):
    """Wired to gr.Chatbot's native .like() event (H.4) -- like_data.index
    is this message's position in the chat pane, like_data.liked is
    thumbs-up (True) or thumbs-down (False). Gradio injects like_data
    automatically for a gr.LikeData-annotated parameter, regardless of
    where it falls in the declared inputs list.
    """
    if conversation_id:
        conn = get_connection()
        save_message_feedback(conn, conversation_id, like_data.index, liked=like_data.liked, reason=reason or None)
        conn.close()
    return ""
