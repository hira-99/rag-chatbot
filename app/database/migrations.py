"""Schema creation and migration."""
from app.database.models import CREATE_CONVERSATIONS_TABLE, CREATE_MESSAGES_TABLE


def run_migrations(conn):
    conn.execute(CREATE_CONVERSATIONS_TABLE)
    conn.execute(CREATE_MESSAGES_TABLE)
    _add_missing_columns(conn)
    conn.commit()


def _add_missing_columns(conn):
    """CREATE TABLE IF NOT EXISTS only helps on a brand new database -- a
    database created before Stage A.4 already has a `messages` table without
    `is_active`, and SQLite has no "ADD COLUMN IF NOT EXISTS". Check first,
    add only what's missing."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
    if "is_active" not in existing_columns:
        conn.execute("ALTER TABLE messages ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
