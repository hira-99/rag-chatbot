"""Application entry point -- wires everything together and launches the UI."""
import gradio as gr

from app.database.connection import get_connection
from app.database.migrations import run_migrations
from app.evaluation.regression import run_all as run_regression
from app.ui.approvals import do_approve, do_reject, refresh_approval_choices
from app.ui.chat import bot_respond, do_feedback, regenerate_response, user_submit
from app.ui.conversations import (
    do_delete,
    do_rename,
    refresh_conversation_choices,
    start_new_conversation,
    switch_conversation,
)
from app.ui.files import do_delete_file, refresh_file_choices, upload_file
from app.ui.memory import (
    do_correct,
    do_disable,
    do_delete as do_delete_memory,
    do_set_consent_mode,
    export_memories,
    load_consent_mode,
    refresh_memory_choices,
)
from app.ui.traces import load_metrics_summary, load_trace_timeline, refresh_trace_choices

_migration_conn = get_connection()
run_migrations(_migration_conn)
_migration_conn.close()


def _run_regression_report():
    report = run_regression()
    lines = [f"Release blocked: {report['release_blocked']}", ""]
    for name, score in report["scores"].items():
        threshold = report["thresholds"][name]
        status = "PASS" if score >= threshold else "FAIL"
        lines.append(f"[{status}] {name}: {score:.2f} (threshold {threshold})")
    return "\n".join(lines)


with gr.Blocks(title="ChatBot Assistant") as demo:
    # None until the user sends a message or picks/creates a conversation --
    # see user_submit's handling of a None conversation_id.
    conversation_id_state = gr.State(None)

    # Chat vs Developer are separate tabs (Section H's explicit requirement:
    # the trace viewer stays out of the user-facing chat pane).
    with gr.Tabs():
        with gr.Tab("Chat"):
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

                    gr.Markdown("### Files")
                    file_upload = gr.File(label="Upload a document (.txt, .md, .html, .pdf)", type="filepath")
                    file_list = gr.Radio(choices=[], show_label=False)
                    delete_file_button = gr.Button("Delete selected file", variant="stop")

                    gr.Markdown("### Approvals")
                    approval_list = gr.Radio(choices=[], show_label=False)
                    with gr.Row():
                        approve_button = gr.Button("Approve")
                        reject_button = gr.Button("Reject", variant="stop")

                    gr.Markdown("### Memory")
                    consent_mode_radio = gr.Radio(
                        choices=["always_ask", "auto_save_non_sensitive", "disabled"],
                        label="Save new memories",
                    )
                    memory_search_box = gr.Textbox(placeholder="Search memories...", show_label=False)
                    memory_list = gr.Radio(choices=[], show_label=False)
                    memory_correction_box = gr.Textbox(label="Correct selected", placeholder="New text...")
                    with gr.Row():
                        memory_correct_button = gr.Button("Save correction")
                        memory_disable_button = gr.Button("Disable")
                        memory_delete_button = gr.Button("Delete", variant="stop")
                    memory_export_box = gr.Textbox(label="Export (JSON)", lines=4, interactive=False)
                    memory_export_button = gr.Button("Export all")

                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(label="Chat")
                    feedback_reason_box = gr.Textbox(
                        label="Feedback reason (optional, before you 👍/👎 a reply)", placeholder="Why?"
                    )
                    with gr.Row():
                        message_box = gr.Textbox(placeholder="Type a message...", show_label=False, scale=4)
                        send_button = gr.Button("Send", scale=1)
                        stop_button = gr.Button("Stop", scale=1)

        with gr.Tab("Developer"):
            gr.Markdown("### Metrics")
            metrics_box = gr.Textbox(label=None, show_label=False, lines=4, interactive=False)
            refresh_metrics_button = gr.Button("Refresh metrics")

            gr.Markdown("### Traces")
            trace_list = gr.Radio(choices=[], show_label=False, label="Recent traces")
            trace_timeline_box = gr.Textbox(label="Spans", lines=16, interactive=False)

            gr.Markdown("### Release gate")
            regression_box = gr.Textbox(label="Regression report", lines=6, interactive=False)
            run_regression_button = gr.Button("Run regression check")

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
        # A turn can create a new pending approval (Section E) -- refresh
        # so it shows up without waiting for the next unrelated event.
        bot_event.then(refresh_approval_choices, [approval_list], [approval_list])
        # A turn can also save new long-term memories (Section F).
        bot_event.then(refresh_memory_choices, [memory_search_box, memory_list], [memory_list])

    # Regenerate: Gradio's built-in retry icon under the last assistant reply.
    # Also cancellable -- it streams a new reply the same way bot_respond does.
    retry_event = chatbot.retry(
        regenerate_response,
        [chatbot, conversation_id_state],
        [chatbot],
    )
    cancellable_events.append(retry_event)
    retry_event.then(refresh_approval_choices, [approval_list], [approval_list])
    retry_event.then(refresh_memory_choices, [memory_search_box, memory_list], [memory_list])
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

    # Quality feedback (H.4): thumbs-up/down on any message, via gr.Chatbot's
    # native .like() event -- optionally preceded by typing a reason.
    chatbot.like(do_feedback, [conversation_id_state, feedback_reason_box], [feedback_reason_box])

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

    # File upload (Section C): the handler persists the attachment row and
    # hands the actual work to the background thread pool immediately, so
    # this returns before ingestion finishes -- the status shown in
    # file_list's label ("uploaded"/"extracting"/.../"ready") only catches
    # up once the poll timer below fires.
    file_upload.upload(upload_file, [file_upload], [file_list])
    delete_file_button.click(do_delete_file, [file_list], [file_list])

    # Poll so in-progress ingestion status (extracting -> chunking ->
    # embedding -> indexing -> ready/failed) shows up without a manual
    # refresh -- there's no push channel from the worker thread to the UI.
    file_status_timer = gr.Timer(2)
    file_status_timer.tick(refresh_file_choices, [file_list], [file_list])

    # Approvals (Section E, Step 20): approving/rejecting resumes the
    # paused agent run and appends its result to whichever conversation it
    # belongs to (see app/ui/approvals.py) -- refresh the sidebar too, since
    # a resumed run may have just generated the conversation's title.
    approve_event = approve_button.click(
        do_approve, [approval_list, chatbot, conversation_id_state], [chatbot, approval_list]
    )
    approve_event.then(refresh_conversation_choices, [search_box, conversation_id_state], [conversation_list])
    reject_event = reject_button.click(
        do_reject, [approval_list, chatbot, conversation_id_state], [chatbot, approval_list]
    )
    reject_event.then(refresh_conversation_choices, [search_box, conversation_id_state], [conversation_list])

    # Memory (Section F): view/search/correct/disable/delete long-term
    # memories, export them, and set the consent mode new memories are
    # saved under. (A turn creating a memory on its own is wired above,
    # next to the bot_event that produces it.)
    memory_search_box.change(refresh_memory_choices, [memory_search_box, memory_list], [memory_list])
    memory_correct_button.click(
        do_correct, [memory_list, memory_correction_box], [memory_list, memory_correction_box]
    )
    memory_disable_button.click(do_disable, [memory_list], [memory_list])
    memory_delete_button.click(do_delete_memory, [memory_list], [memory_list])
    memory_export_button.click(export_memories, None, [memory_export_box])
    consent_mode_radio.change(do_set_consent_mode, [consent_mode_radio], [consent_mode_radio])

    # Developer tab (Section H): metrics/traces are read-only views over
    # what tracing already recorded; the regression check runs the real
    # evaluation suite on demand (this can take a while -- several model
    # calls -- so it's a button, not something auto-refreshed).
    refresh_metrics_button.click(load_metrics_summary, None, [metrics_box])
    trace_list.change(load_trace_timeline, [trace_list], [trace_timeline_box])
    run_regression_button.click(_run_regression_report, None, [regression_box])

    # Populate the sidebar once per session.
    demo.load(refresh_conversation_choices, None, [conversation_list])
    demo.load(refresh_file_choices, None, [file_list])
    demo.load(refresh_approval_choices, None, [approval_list])
    demo.load(refresh_memory_choices, None, [memory_list])
    demo.load(load_consent_mode, None, [consent_mode_radio])
    demo.load(load_metrics_summary, None, [metrics_box])
    demo.load(refresh_trace_choices, None, [trace_list])

if __name__ == "__main__":
    demo.launch()
