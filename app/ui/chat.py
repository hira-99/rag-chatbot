"""Gradio chat interface: token streaming, tool-progress events, cancellation."""
from app.llm.client import stream_chat_completion


def respond(message, history):
    """Gradio ChatInterface streaming function.

    `history` is a list of {"role": ..., "content": ...} dicts (Gradio's
    messages format). We turn it plus the new user message into the plain
    OpenAI messages list and stream the reply back.

    NOTE for Stage A.2: the response is only "complete" once this generator
    finishes normally (falls off the end of the for-loop below) rather than
    being interrupted. Persistence should hook in at that point, not on
    every intermediate yield -- writing partial text to the database on
    every token would mean a cancelled/failed stream leaves a half-written
    message behind.
    """
    messages = list(history) + [{"role": "user", "content": message}]

    partial_response = ""
    for delta in stream_chat_completion(messages):
        partial_response += delta
        yield partial_response
