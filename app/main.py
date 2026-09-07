"""Application entry point -- wires everything together and launches the UI."""
import gradio as gr

from app.database.connection import get_connection
from app.database.migrations import run_migrations
from app.ui.chat import bot_respond, regenerate_response, user_submit
from app.ui.conversations import (
    do_delete,
    do_rename,
    refresh_conversation_choices,
    start_new_conversation,
    switch_conversation,
)

_migration_conn = get_connection()
run_migrations(_migration_conn)
_migration_conn.close()


with gr.Blocks(title="ChatBot Assistant") as demo:
    # None until the user sends a message or picks/creates a conversation --
    # see user_submit's handling of a None conversation_id.
    conversation_id_state = gr.State(None)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Conversations")
            new_button = gr.Button("+ New Conversation")
            search_box = gr.Textbox(placeholder="Search conversations...", show_label=False)
            conversation_list = gr.Radio(choices=[], show_label=False)

            gr.Markdown("---")
            rename_box = gr.Textbox(label="Rename selected", placeholder="New title...")
            rename_button = gr.Button("Rename")
            delete_button = gr.Button("Delete selected", variant="stop")

        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="Chat")
            with gr.Row():
                message_box = gr.Textbox(placeholder="Type a message...", show_label=False, scale=4)
                send_button = gr.Button("Send", scale=1)
                stop_button = gr.Button("Stop", scale=1)

    # Sending a message (Enter key or the Send button): persist + echo the
    # user's turn, then stream + persist the reply (title gets generated
    # inside bot_respond on the first exchange), then refresh the sidebar so
    # a new/renamed title shows up.
    #
    # Only the bot_respond step is captured for cancellation below -- it's
    # the only long-running one; user_submit and refresh_conversation_choices
    # are effectively instant.
    cancellable_events = []
    send_triggers = [message_box.submit, send_button.click]
    for trigger in send_triggers:
        bot_event = trigger(
            user_submit,
            [message_box, chatbot, conversation_id_state],
            [message_box, chatbot, conversation_id_state],
        ).then(
            bot_respond,
            [chatbot, conversation_id_state],
            [chatbot],
        )
        cancellable_events.append(bot_event)
        bot_event.then(
            refresh_conversation_choices,
            [search_box, conversation_id_state],
            [conversation_list],
        )

    # Regenerate: Gradio's built-in retry icon under the last assistant reply.
    # Also cancellable -- it streams a new reply the same way bot_respond does.
    retry_event = chatbot.retry(
        regenerate_response,
        [chatbot, conversation_id_state],
        [chatbot],
    )
    cancellable_events.append(retry_event)
    retry_event.then(
        refresh_conversation_choices,
        [search_box, conversation_id_state],
        [conversation_list],
    )

    # Cancellation (roadmap A.6): stops whichever of the above is currently
    # running. Model streaming is the only long-running operation that
    # exists in the app so far -- retrieval, tool execution, agent planning,
    # and MCP calls will each need their own entry in cancellable_events once
    # those stages add them. "Mark status accurately" here means the
    # database, not the chat bubble: bot_respond only persists a reply once
    # its loop finishes normally (see its docstring) -- cancelling raises
    # GeneratorExit at the current yield, so the code that would save the
    # reply never runs. The partial text stays on screen, but nothing false
    # is written to the database.
    stop_button.click(fn=None, cancels=cancellable_events)

    # Selecting a conversation loads it into the chat pane.
    conversation_list.change(
        switch_conversation,
        [conversation_list],
        [chatbot, conversation_id_state],
    )

    # Search filters the sidebar list live, without losing track of which
    # conversation is still open (see refresh_conversation_choices).
    search_box.change(
        refresh_conversation_choices,
        [search_box, conversation_id_state],
        [conversation_list],
    )

    # New conversation: clear the chat pane, get a fresh (unsaved) conversation_id,
    # and clear the sidebar's own selection (see start_new_conversation).
    new_button.click(start_new_conversation, None, [conversation_id_state, chatbot, conversation_list])

    # Rename / delete act on whichever conversation is currently open.
    rename_button.click(do_rename, [conversation_id_state, rename_box], [conversation_list, rename_box])
    delete_button.click(do_delete, [conversation_id_state], [conversation_list, conversation_id_state, chatbot])

    # Populate the sidebar once per session.
    demo.load(refresh_conversation_choices, None, [conversation_list])

if __name__ == "__main__":
    demo.launch()
