"""Human-in-the-loop approval gate for sensitive tools (Step 20).

A pending approval is a plain database row -- the agent loop stops and
waits for a real UI action (app/ui/approvals.py). Model-generated text
claiming "the user approved this" is never treated as authorization; only
a click against one of these rows is.
"""
import json

from app.database.connection import get_connection
from app.database.models import create_pending_approval, update_approval_status


def request_approval(run_id, conversation_id, user_id, pending_tool_call, messages):
    """Persists the in-flight run (messages + which call is pending, id
    included so the resumed tool-result message lines up with the model's
    original tool_call_id) so approving/rejecting later -- a separate UI
    action, possibly much later -- can resume the run from exactly where
    it paused."""
    run_state = json.dumps({"messages": messages, "pending_tool_call": pending_tool_call})
    conn = get_connection()
    approval_id = create_pending_approval(
        conn, run_id, conversation_id, user_id,
        pending_tool_call["name"], json.dumps(pending_tool_call["arguments"]), run_state,
    )
    conn.close()
    return approval_id


def mark_approved(approval_id):
    conn = get_connection()
    update_approval_status(conn, approval_id, "approved")
    conn.close()


def mark_rejected(approval_id):
    conn = get_connection()
    update_approval_status(conn, approval_id, "rejected")
    conn.close()
