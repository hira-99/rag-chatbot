"""Approval UI: show pending tool actions, approve/reject, resume the run."""
import json

import gradio as gr

from app.agent.loop import resume_after_approval
from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import add_message, get_pending_approval, list_pending_approvals
from app.llm.token_counter import count_tokens
from app.tools.approvals import mark_approved, mark_rejected


def refresh_approval_choices(selected_approval_id=None):
    conn = get_connection()
    approvals = list_pending_approvals(conn, DEFAULT_USER_ID)
    conn.close()
    choices = [(f"{a['tool_name']}({a['arguments']})", a["approval_id"]) for a in approvals]
    return gr.update(choices=choices, value=selected_approval_id)


def _resume_and_persist(approval, approved):
    run_state = json.loads(approval["run_state"])
    conversation_id = approval["conversation_id"]

    final_text = ""
    for event in resume_after_approval(
        run_state["messages"], run_state["pending_tool_call"],
        DEFAULT_USER_ID, approval["run_id"], conversation_id, approved=approved,
    ):
        if event["status"] == "done":
            final_text = event["text"]
        elif event["status"] == "awaiting_approval":
            # A second sensitive call was requested -- queue it too and
            # stop here rather than silently executing it.
            from app.tools.approvals import request_approval
            request_approval(approval["run_id"], conversation_id, DEFAULT_USER_ID, event["pending_tool_call"], event["messages"])
            final_text = "This action needs another approval before I can continue -- check the Approvals list."

    conn = get_connection()
    add_message(conn, conversation_id, DEFAULT_USER_ID, "assistant", final_text, token_count=count_tokens(final_text))
    conn.close()
    return final_text, conversation_id


def _apply(approval_id, chatbot_history, conversation_id, approved):
    if not approval_id:
        return chatbot_history, refresh_approval_choices()

    conn = get_connection()
    approval = get_pending_approval(conn, approval_id)
    conn.close()
    if not approval or approval["status"] != "pending":
        return chatbot_history, refresh_approval_choices()

    if approved:
        mark_approved(approval_id)
    else:
        mark_rejected(approval_id)
    final_text, approval_conversation_id = _resume_and_persist(approval, approved=approved)

    # The reply is always persisted to its own conversation; only reflect
    # it in the visible chat pane if that's the conversation still open --
    # otherwise it'll show correctly next time that conversation is opened.
    if approval_conversation_id == conversation_id:
        chatbot_history = chatbot_history + [{"role": "assistant", "content": final_text}]
    return chatbot_history, refresh_approval_choices()


def do_approve(approval_id, chatbot_history, conversation_id):
    return _apply(approval_id, chatbot_history, conversation_id, approved=True)


def do_reject(approval_id, chatbot_history, conversation_id):
    return _apply(approval_id, chatbot_history, conversation_id, approved=False)
