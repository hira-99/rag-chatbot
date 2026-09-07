"""users, conversations, messages, agent_runs, tool_calls, citations, attachments.

Only `conversations` and `messages` exist so far (Stage A.2). The rest get
added when a later stage actually needs them -- building `agent_runs` /
`tool_calls` / `citations` / `attachments` now would mean guessing their
shape before any code exercises them.
"""
import uuid
from datetime import datetime, timezone

CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    token_count INTEGER,
    run_id TEXT
)
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def new_conversation_id():
    """Just an ID -- no database row yet. Cheap to call as many times as
    Gradio's gr.State happens to call it (see get_or_create_conversation)."""
    return uuid.uuid4().hex


def get_or_create_conversation(conn, conversation_id, user_id, title):
    """Create the conversation row on first use. INSERT OR IGNORE means a
    conversation_id that already exists is a no-op, not an error -- callers
    don't need to check existence first."""
    timestamp = _now()
    conn.execute(
        "INSERT OR IGNORE INTO conversations (conversation_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, user_id, title, timestamp, timestamp),
    )
    conn.commit()


def add_message(conn, conversation_id, user_id, role, content, token_count=None, run_id=None):
    message_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO messages (message_id, conversation_id, user_id, role, content, created_at, token_count, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, conversation_id, user_id, role, content, _now(), token_count, run_id),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
        (_now(), conversation_id),
    )
    conn.commit()
    return message_id


def get_messages(conn, conversation_id):
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_conversations(conn, user_id, search_query=None):
    """All of a user's conversations, most recently active first. `search_query`
    filters by title -- "view previous conversations" and "search conversation
    titles" are the same query with an optional extra clause."""
    if search_query:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? AND title LIKE ? ORDER BY updated_at DESC",
            (user_id, f"%{search_query}%"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def rename_conversation(conn, conversation_id, new_title):
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
        (new_title, _now(), conversation_id),
    )
    conn.commit()


def delete_conversation(conn, conversation_id):
    """Messages aren't ON DELETE CASCADE in the schema, so delete them
    explicitly first -- otherwise they'd be orphaned, not removed."""
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
    conn.commit()
