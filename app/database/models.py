"""users, conversations, messages, tool_calls, pending_approvals, customers,
attachments, memories, conversation_summaries, memory_settings, trace_spans,
message_feedback, citations.

`citations` isn't needed as a table -- Section D validates citations against
the sources given for that one turn, nothing persists them separately.
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
    run_id TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
)
"""

# status moves: uploaded -> extracting -> chunking -> embedding -> indexing
# -> ready | failed (roadmap C.3). is_active lets a re-upload of the same
# filename supersede the old version (C.5) without losing the audit trail --
# same pattern as messages.is_active.
CREATE_ATTACHMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size INTEGER,
    content_hash TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_message TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
)
"""

# Illustrative fixture data, not user data -- seeded by run_migrations so
# the customer-lookup tool (E.1) always has something real to look up.
CREATE_CUSTOMERS_TABLE = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL,
    signup_date TEXT NOT NULL
)
"""

# Every tool call an agent run makes, keyed for idempotency (executor.py) so
# a regenerate or a resumed run reuses a prior result instead of re-running
# a sensitive action -- also doubles as the audit trail (G.6).
CREATE_TOOL_CALLS_TABLE = """
CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id TEXT PRIMARY KEY,
    run_id TEXT,
    conversation_id TEXT,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    result TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
)
"""

# A tool the registry marks requires_approval stops the agent loop instead
# of executing (Step 20) -- run_state is the serialized in-flight messages
# + pending tool call, so approving/rejecting later (a separate UI action,
# possibly much later) can resume the run from exactly where it paused.
CREATE_PENDING_APPROVALS_TABLE = """
CREATE TABLE IF NOT EXISTS pending_approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    run_state TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
)
"""

# scope: 'personal' (only this user_id) or 'org' (every user, for the
# future multi-user case -- see app/memory/permissions.py). embedding is a
# JSON-encoded float list; Step 14's own notebook found a plain table plus
# Python cosine similarity simpler than running a vector DB for this few
# rows per user. is_active/superseded_by is the same supersede-not-overwrite
# pattern as messages/attachments (Step 14.9's conflict resolution).
CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    memory_text TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'personal',
    embedding TEXT NOT NULL,
    source_conversation_id TEXT,
    confidence REAL,
    is_active INTEGER NOT NULL DEFAULT 1,
    superseded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

# One row per conversation -- archived_through_count is how many of the
# conversation's (non-system) messages are already folded into
# summary_text, so the summarizer only ever processes newly archived
# messages instead of resummarizing from scratch (Step 13.6).
CREATE_CONVERSATION_SUMMARIES_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_summaries (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(conversation_id),
    summary_text TEXT NOT NULL DEFAULT '',
    archived_through_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)
"""

CREATE_MEMORY_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_settings (
    user_id TEXT PRIMARY KEY,
    consent_mode TEXT NOT NULL DEFAULT 'auto_save_non_sensitive'
)
"""

# One row per operation inside a turn (Step 25.1-25.2): trace_id groups
# every span for one user turn, span_id/parent_span_id nest them (a turn
# span containing a retrieval span and a model_call span, say).
# input_summary/output_summary are already redacted by the time they get
# here (app/observability/redaction.py) -- this table is not the place to
# redact, logging.py is.
CREATE_TRACE_SPANS_TABLE = """
CREATE TABLE IF NOT EXISTS trace_spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_span_id TEXT,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    span_type TEXT NOT NULL,
    name TEXT NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    status TEXT NOT NULL DEFAULT 'ok',
    error_category TEXT,
    duration_ms REAL,
    cost_usd REAL,
    started_at TEXT NOT NULL
)
"""

# H.4: thumbs-up/down + optional reason on an assistant message, keyed by
# its position in the conversation (gr.Chatbot's native .like() event gives
# an index, not a message_id) rather than a separate message table join.
CREATE_MESSAGE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS message_feedback (
    feedback_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    liked INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
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


def get_messages(conn, conversation_id, include_replaced=False):
    """Active messages only by default -- a response that's been regenerated
    (is_active=0, see mark_last_assistant_message_replaced) shouldn't show up
    in the chat pane or be sent to the model. `include_replaced=True` is for
    audit/debugging, not normal use."""
    if include_replaced:
        query = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at"
    else:
        query = "SELECT * FROM messages WHERE conversation_id = ? AND is_active = 1 ORDER BY created_at"
    rows = conn.execute(query, (conversation_id,)).fetchall()
    return [dict(row) for row in rows]


def mark_last_assistant_message_replaced(conn, conversation_id):
    """Response regeneration: mark the current assistant reply as replaced
    (is_active=0) rather than deleting it -- the old response stays in the
    database for audit, it just stops being shown or sent to the model."""
    row = conn.execute(
        """
        SELECT message_id FROM messages
        WHERE conversation_id = ? AND role = 'assistant' AND is_active = 1
        ORDER BY created_at DESC LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if row:
        conn.execute("UPDATE messages SET is_active = 0 WHERE message_id = ?", (row["message_id"],))
        conn.commit()


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


def create_attachment(conn, attachment_id, user_id, filename, mime_type, size, content_hash, conversation_id=None):
    conn.execute(
        """
        INSERT INTO attachments (attachment_id, user_id, conversation_id, filename, mime_type, size, content_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (attachment_id, user_id, conversation_id, filename, mime_type, size, content_hash, _now()),
    )
    conn.commit()


def update_attachment_status(conn, attachment_id, status, error_message=None, chunk_count=None):
    if chunk_count is not None:
        conn.execute(
            "UPDATE attachments SET status = ?, error_message = ?, chunk_count = ? WHERE attachment_id = ?",
            (status, error_message, chunk_count, attachment_id),
        )
    else:
        conn.execute(
            "UPDATE attachments SET status = ?, error_message = ? WHERE attachment_id = ?",
            (status, error_message, attachment_id),
        )
    conn.commit()


def get_attachment(conn, attachment_id):
    row = conn.execute("SELECT * FROM attachments WHERE attachment_id = ?", (attachment_id,)).fetchone()
    return dict(row) if row else None


def list_attachments(conn, user_id, include_inactive=False):
    if include_inactive:
        query = "SELECT * FROM attachments WHERE user_id = ? ORDER BY created_at DESC"
    else:
        query = "SELECT * FROM attachments WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC"
    rows = conn.execute(query, (user_id,)).fetchall()
    return [dict(row) for row in rows]


def find_active_attachment_by_filename(conn, user_id, filename):
    row = conn.execute(
        "SELECT * FROM attachments WHERE user_id = ? AND filename = ? AND is_active = 1",
        (user_id, filename),
    ).fetchone()
    return dict(row) if row else None


def supersede_attachment(conn, attachment_id):
    """A re-upload of the same filename replaces the old version (C.5) --
    mark it inactive rather than deleting, same reasoning as regenerated
    messages: the old attachment stays for audit, it just stops being
    listed or retrieved from."""
    conn.execute("UPDATE attachments SET is_active = 0 WHERE attachment_id = ?", (attachment_id,))
    conn.commit()


def delete_attachment(conn, attachment_id):
    """Explicit user-initiated deletion (C.6) -- hard delete, unlike
    supersede_attachment. Caller is responsible for also removing the
    attachment's chunks from the retrieval stores."""
    conn.execute("DELETE FROM attachments WHERE attachment_id = ?", (attachment_id,))
    conn.commit()


CUSTOMER_FIXTURES = [
    ("CUST-1001", "Alex Rivera", "alex.rivera@northwind.example", "Pro", "active", "2023-02-14"),
    ("CUST-1002", "Priya Natarajan", "priya.n@caldera.example", "Enterprise", "active", "2022-09-01"),
    ("CUST-1003", "Jordan Blake", "jordan.blake@fernbridge.example", "Starter", "active", "2024-06-20"),
    ("CUST-1004", "Sam Okafor", "sam.okafor@lumenworks.example", "Pro", "past_due", "2023-11-05"),
    ("CUST-1005", "Ines Duarte", "ines.duarte@haloforge.example", "Enterprise", "cancelled", "2021-05-30"),
]


def seed_customers(conn):
    conn.executemany(
        "INSERT OR IGNORE INTO customers (customer_id, name, email, plan, status, signup_date) VALUES (?, ?, ?, ?, ?, ?)",
        CUSTOMER_FIXTURES,
    )
    conn.commit()


def get_customer(conn, customer_id):
    row = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    return dict(row) if row else None


def record_tool_call(conn, tool_call_id, run_id, conversation_id, user_id, tool_name, arguments, result, idempotency_key):
    conn.execute(
        """
        INSERT INTO tool_calls (tool_call_id, run_id, conversation_id, user_id, tool_name, arguments, result, idempotency_key, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tool_call_id, run_id, conversation_id, user_id, tool_name, arguments, result, idempotency_key, _now()),
    )
    conn.commit()


def find_tool_call_by_idempotency_key(conn, idempotency_key):
    row = conn.execute("SELECT * FROM tool_calls WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    return dict(row) if row else None


def create_pending_approval(conn, run_id, conversation_id, user_id, tool_name, arguments, run_state):
    approval_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO pending_approvals (approval_id, run_id, conversation_id, user_id, tool_name, arguments, run_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (approval_id, run_id, conversation_id, user_id, tool_name, arguments, run_state, _now()),
    )
    conn.commit()
    return approval_id


def get_pending_approval(conn, approval_id):
    row = conn.execute("SELECT * FROM pending_approvals WHERE approval_id = ?", (approval_id,)).fetchone()
    return dict(row) if row else None


def list_pending_approvals(conn, user_id):
    rows = conn.execute(
        "SELECT * FROM pending_approvals WHERE user_id = ? AND status = 'pending' ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_approval_status(conn, approval_id, status):
    conn.execute("UPDATE pending_approvals SET status = ? WHERE approval_id = ?", (status, approval_id))
    conn.commit()


def save_memory_row(conn, user_id, memory_text, memory_type, embedding_json, scope="personal", source_conversation_id=None, confidence=None):
    memory_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO memories (memory_id, user_id, memory_text, memory_type, scope, embedding, source_conversation_id, confidence, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (memory_id, user_id, memory_text, memory_type, scope, embedding_json, source_conversation_id, confidence, _now(), _now()),
    )
    conn.commit()
    return memory_id


def list_memories(conn, user_id, include_inactive=False):
    """Memories this user created, any scope -- the management view
    (app/ui/memory.py): view/correct/delete acts on what you made."""
    query = "SELECT * FROM memories WHERE user_id = ?"
    if not include_inactive:
        query += " AND is_active = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, (user_id,)).fetchall()
    return [dict(row) for row in rows]


def list_memories_for_retrieval(conn, user_id):
    """Memories relevant TO this user: their own personal memories, plus
    every 'org' memory regardless of who created it -- real scope
    isolation (F.5), exercised even with one real user. A personal memory
    never crosses the user_id boundary; an org one is shared by design."""
    rows = conn.execute(
        "SELECT * FROM memories WHERE is_active = 1 AND ((scope = 'personal' AND user_id = ?) OR scope = 'org')",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_memory(conn, memory_id):
    row = conn.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,)).fetchone()
    return dict(row) if row else None


def update_memory_text(conn, memory_id, new_text, embedding_json):
    conn.execute(
        "UPDATE memories SET memory_text = ?, embedding = ?, updated_at = ? WHERE memory_id = ?",
        (new_text, embedding_json, _now(), memory_id),
    )
    conn.commit()


def supersede_memory(conn, old_memory_id, new_memory_id):
    conn.execute("UPDATE memories SET is_active = 0, superseded_by = ? WHERE memory_id = ?", (new_memory_id, old_memory_id))
    conn.commit()


def disable_memory(conn, memory_id):
    conn.execute("UPDATE memories SET is_active = 0 WHERE memory_id = ?", (memory_id,))
    conn.commit()


def delete_memory(conn, memory_id):
    conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
    conn.commit()


def get_conversation_summary(conn, conversation_id):
    row = conn.execute("SELECT * FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,)).fetchone()
    return dict(row) if row else None


def save_conversation_summary(conn, conversation_id, summary_text, archived_through_count):
    conn.execute(
        """
        INSERT INTO conversation_summaries (conversation_id, summary_text, archived_through_count, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(conversation_id) DO UPDATE SET
            summary_text = excluded.summary_text,
            archived_through_count = excluded.archived_through_count,
            updated_at = excluded.updated_at
        """,
        (conversation_id, summary_text, archived_through_count, _now()),
    )
    conn.commit()


def get_consent_mode(conn, user_id):
    row = conn.execute("SELECT consent_mode FROM memory_settings WHERE user_id = ?", (user_id,)).fetchone()
    return row["consent_mode"] if row else "auto_save_non_sensitive"


def set_consent_mode(conn, user_id, mode):
    conn.execute(
        """
        INSERT INTO memory_settings (user_id, consent_mode) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET consent_mode = excluded.consent_mode
        """,
        (user_id, mode),
    )
    conn.commit()


def get_audit_trail(conn, user_id, limit=100):
    """The storage side (tool_calls, pending_approvals) already records
    every tool execution and approval decision as it happens -- this is
    the query side (G.6): one merged, time-ordered view across both, for
    accountability review. app/ui/traces.py (Section H) is the actual
    viewer; this is what it queries.
    """
    tool_call_rows = conn.execute(
        "SELECT tool_call_id AS event_id, created_at, tool_name, arguments, result, 'executed' AS event_type "
        "FROM tool_calls WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    approval_rows = conn.execute(
        "SELECT approval_id AS event_id, created_at, tool_name, arguments, status AS result, 'approval_' || status AS event_type "
        "FROM pending_approvals WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()

    events = [dict(row) for row in tool_call_rows] + [dict(row) for row in approval_rows]
    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events[:limit]


def save_trace_span(conn, span_id, trace_id, parent_span_id, user_id, conversation_id, span_type, name,
                     input_summary, output_summary, status, error_category, duration_ms, cost_usd, started_at):
    conn.execute(
        """
        INSERT INTO trace_spans (span_id, trace_id, parent_span_id, user_id, conversation_id, span_type, name,
                                  input_summary, output_summary, status, error_category, duration_ms, cost_usd, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (span_id, trace_id, parent_span_id, user_id, conversation_id, span_type, name,
         input_summary, output_summary, status, error_category, duration_ms, cost_usd, started_at),
    )
    conn.commit()


def list_recent_traces(conn, user_id, limit=20):
    """One row per trace_id -- the top-level turn span (parent_span_id IS
    NULL) for each of the user's most recent traces, for the trace list view."""
    rows = conn.execute(
        """
        SELECT * FROM trace_spans
        WHERE user_id = ? AND parent_span_id IS NULL
        ORDER BY started_at DESC LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_trace_spans(conn, trace_id):
    rows = conn.execute(
        "SELECT * FROM trace_spans WHERE trace_id = ? ORDER BY started_at",
        (trace_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_all_spans(conn, user_id, span_type=None):
    """For aggregate metrics (Step 25.8) -- every span of a given type
    across all of a user's traces, not grouped by trace."""
    if span_type:
        rows = conn.execute(
            "SELECT * FROM trace_spans WHERE user_id = ? AND span_type = ? ORDER BY started_at",
            (user_id, span_type),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM trace_spans WHERE user_id = ? ORDER BY started_at", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def save_message_feedback(conn, conversation_id, message_index, liked, reason=None):
    feedback_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO message_feedback (feedback_id, conversation_id, message_index, liked, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (feedback_id, conversation_id, message_index, int(liked), reason, _now()),
    )
    conn.commit()
    return feedback_id
