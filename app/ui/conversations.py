"""Conversation management: create, rename, delete, search, continue."""
import gradio as gr

from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    delete_conversation,
    get_messages,
    list_conversations,
    new_conversation_id,
    rename_conversation,
)


def refresh_conversation_choices(search_query=None, selected_conversation_id=None):
    """Update the sidebar Radio's `choices` -- (label, value) pairs.

    Must return gr.update(choices=...), not a bare list: a bare list/tuple
    returned to a component output is interpreted as the component's VALUE,
    not its choices -- returning [] that way crashes Radio's preprocessing
    ("Value: [] is not in the list of choices: []") the moment there are no
    conversations yet.

    `selected_conversation_id`, when given, also sets which row shows as
    selected -- without this, sending a message in a brand new conversation
    would refresh the list but leave the *previous* conversation looking
    selected, which is misleading (they're not the same conversation).
    """
    conn = get_connection()
    conversations = list_conversations(conn, DEFAULT_USER_ID, search_query)
    conn.close()
    choices = [(c["title"], c["conversation_id"]) for c in conversations]
    return gr.update(choices=choices, value=selected_conversation_id)


def load_conversation_messages(conversation_id):
    """DB rows -> Gradio Chatbot's messages format ({"role", "content"} dicts)."""
    if not conversation_id:
        return []
    conn = get_connection()
    rows = get_messages(conn, conversation_id)
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def switch_conversation(conversation_id):
    """Selecting a conversation in the sidebar: load its messages, and make
    it the open conversation."""
    return load_conversation_messages(conversation_id), conversation_id


def start_new_conversation():
    """A fresh, not-yet-persisted conversation_id and an empty chat pane.
    No database row until the first message (same lazy-creation reasoning
    as A.2) -- so clicking "New" repeatedly never litters the sidebar with
    empty conversations.

    Also clears the sidebar Radio's own selected value -- without this, the
    Radio keeps showing the *previous* conversation as selected (it was
    never told otherwise), and clicking that same still-highlighted row
    again does nothing, because Gradio's .change() only fires on an actual
    value change.
    """
    return new_conversation_id(), [], gr.update(value=None)


def do_rename(conversation_id, new_title):
    if conversation_id and new_title.strip():
        conn = get_connection()
        rename_conversation(conn, conversation_id, new_title.strip())
        conn.close()
    # Keep the just-renamed conversation selected -- it still exists, only its label changed.
    return refresh_conversation_choices(selected_conversation_id=conversation_id), ""


def do_delete(conversation_id):
    """Returns the refreshed choice list, plus a cleared chat pane and a
    fresh (unsaved) conversation_id -- deleting the open conversation
    shouldn't leave the UI pointing at a conversation_id that no longer
    exists in the database."""
    if conversation_id:
        conn = get_connection()
        delete_conversation(conn, conversation_id)
        conn.close()
    new_id, empty_history, _ = start_new_conversation()
    return refresh_conversation_choices(), new_id, empty_history
