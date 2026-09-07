"""Schema creation and migration."""
from app.database.models import (
    CREATE_ATTACHMENTS_TABLE,
    CREATE_CONVERSATION_SUMMARIES_TABLE,
    CREATE_CONVERSATIONS_TABLE,
    CREATE_CUSTOMERS_TABLE,
    CREATE_MEMORIES_TABLE,
    CREATE_MEMORY_SETTINGS_TABLE,
    CREATE_MESSAGE_FEEDBACK_TABLE,
    CREATE_MESSAGES_TABLE,
    CREATE_PENDING_APPROVALS_TABLE,
    CREATE_TOOL_CALLS_TABLE,
    CREATE_TRACE_SPANS_TABLE,
    seed_customers,
)


def run_migrations(conn):
    conn.execute(CREATE_CONVERSATIONS_TABLE)
    conn.execute(CREATE_MESSAGES_TABLE)
    conn.execute(CREATE_ATTACHMENTS_TABLE)
    conn.execute(CREATE_CUSTOMERS_TABLE)
    conn.execute(CREATE_TOOL_CALLS_TABLE)
    conn.execute(CREATE_PENDING_APPROVALS_TABLE)
    conn.execute(CREATE_MEMORIES_TABLE)
    conn.execute(CREATE_CONVERSATION_SUMMARIES_TABLE)
    conn.execute(CREATE_MEMORY_SETTINGS_TABLE)
    conn.execute(CREATE_TRACE_SPANS_TABLE)
    conn.execute(CREATE_MESSAGE_FEEDBACK_TABLE)
    _add_missing_columns(conn)
    conn.commit()
    seed_customers(conn)


def _add_missing_columns(conn):
    """CREATE TABLE IF NOT EXISTS only helps on a brand new database -- a
    database created before Stage A.4 already has a `messages` table without
    `is_active`, and SQLite has no "ADD COLUMN IF NOT EXISTS". Check first,
    add only what's missing."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
    if "is_active" not in existing_columns:
        conn.execute("ALTER TABLE messages ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
