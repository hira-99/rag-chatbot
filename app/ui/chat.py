"""Gradio chat interface: token streaming, tool-progress events, cancellation."""
import gradio as gr

from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    add_message,
    get_messages,
    get_or_create_conversation,
    mark_last_assistant_message_replaced,
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


def regenerate_response(retry_data: gr.RetryData, chatbot_history, conversation_id):
    """Wired to Gradio Chatbot's native .retry() event (main.py) -- fires
    when the user clicks the retry icon under the last assistant reply.

    retry_data.index is the index of the USER message whose reply is being
    regenerated (confirmed by testing live -- Gradio's own docstring example
    is misleading about this). Truncating to that index keeps everything up
    to and including that user message, dropping the old reply.

    The old reply is marked replaced (is_active=0), not deleted -- the
    roadmap's "mark it replaced" option, chosen over full branching to keep
    this stage's scope manageable; the previous response is still in the
    database for audit, just not shown or sent to the model again.

    NOTE for when tools exist (a later stage): this must regenerate only the
    model's reasoning/response, never re-execute tool calls that already
    happened for this turn -- reuse their recorded results instead of
    calling send_email etc. a second time.
    """
    conn = get_connection()
    mark_last_assistant_message_replaced(conn, conversation_id)
    conn.close()

    truncated_history = chatbot_history[: retry_data.index + 1]
    yield from bot_respond(truncated_history, conversation_id)
