"""Schema creation and migration."""
from app.database.models import CREATE_CONVERSATIONS_TABLE, CREATE_MESSAGES_TABLE


def run_migrations(conn):
    conn.execute(CREATE_CONVERSATIONS_TABLE)
    conn.execute(CREATE_MESSAGES_TABLE)
    conn.commit()
