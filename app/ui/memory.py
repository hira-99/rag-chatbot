"""Memory UI: view/search/correct/delete/disable long-term memories,
export, and set the consent mode (Step 14.10)."""
import json

import gradio as gr

from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    delete_memory,
    disable_memory,
    get_consent_mode,
    list_memories,
    set_consent_mode,
    update_memory_text,
)
from app.retrieval.embeddings import get_embedding


def refresh_memory_choices(search_query=None, selected_memory_id=None):
    # include_inactive so a disabled memory stays reachable to permanently
    # delete -- otherwise "Disable" would make it vanish from this list
    # with no way back to it (confirmed live: it did, before this fix).
    conn = get_connection()
    memories = list_memories(conn, DEFAULT_USER_ID, include_inactive=True)
    conn.close()
    if search_query:
        memories = [m for m in memories if search_query.lower() in m["memory_text"].lower()]
    choices = [
        (f"[{m['memory_type']}]{'  (disabled)' if not m['is_active'] else ''} {m['memory_text'][:60]}", m["memory_id"])
        for m in memories
    ]
    return gr.update(choices=choices, value=selected_memory_id)


def do_correct(memory_id, new_text):
    if memory_id and new_text.strip():
        embedding = get_embedding(new_text.strip())
        conn = get_connection()
        update_memory_text(conn, memory_id, new_text.strip(), json.dumps(embedding))
        conn.close()
    return refresh_memory_choices(selected_memory_id=memory_id), ""


def do_disable(memory_id):
    if memory_id:
        conn = get_connection()
        disable_memory(conn, memory_id)
        conn.close()
    return refresh_memory_choices()


def do_delete(memory_id):
    if memory_id:
        conn = get_connection()
        delete_memory(conn, memory_id)
        conn.close()
    return refresh_memory_choices()


def export_memories():
    conn = get_connection()
    memories = list_memories(conn, DEFAULT_USER_ID)
    conn.close()
    return json.dumps(
        [{"text": m["memory_text"], "type": m["memory_type"], "created_at": m["created_at"]} for m in memories],
        indent=2,
    )


def load_consent_mode():
    conn = get_connection()
    mode = get_consent_mode(conn, DEFAULT_USER_ID)
    conn.close()
    return mode


def do_set_consent_mode(mode):
    conn = get_connection()
    set_consent_mode(conn, DEFAULT_USER_ID, mode)
    conn.close()
    return mode
