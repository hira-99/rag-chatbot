"""Gradio chat interface: token streaming, tool-progress events, cancellation."""
from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    add_message,
    get_messages,
    get_or_create_conversation,
    new_conversation_id,
    rename_conversation,
)
from app.llm.client import generate_title, stream_chat_completion
from app.llm.token_counter import count_tokens


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


def bot_respond(chatbot_history, conversation_id):
    """Runs second (chained after user_submit): stream the reply into the
    chat pane, persist it once the stream finishes normally, and generate a
    title if this was the conversation's first exchange."""
    plain_messages = [{"role": m["role"], "content": m["content"]} for m in chatbot_history]

    chatbot_history = chatbot_history + [{"role": "assistant", "content": ""}]
    partial_response = ""
    for delta in stream_chat_completion(plain_messages):
        partial_response += delta
        chatbot_history[-1]["content"] = partial_response
        yield chatbot_history

    conn = get_connection()
    add_message(
        conn, conversation_id, DEFAULT_USER_ID, "assistant", partial_response,
        token_count=count_tokens(partial_response),
    )

    # First exchange in this conversation (1 user + 1 assistant message so far)?
    # Generate a real title instead of leaving it as "New conversation".
    if len(get_messages(conn, conversation_id)) == 2:
        user_message = plain_messages[-1]["content"]
        title = generate_title(user_message, partial_response)
        rename_conversation(conn, conversation_id, title)

    conn.close()
