import gradio as gr

from chatbot import chat, clear_conversation, get_request_stats, get_session_stats
from state import create_initial_state

with gr.Blocks() as demo:

    state = gr.State(create_initial_state())

    request_stats = gr.Markdown(get_request_stats())

    session_stats = gr.Markdown(
        get_session_stats(create_initial_state()["usage"])
    )

    chat_interface = gr.ChatInterface(
        fn=chat,
        title="Framework Free Chatbot",
        description="My first chatbot :p",
        additional_inputs=[state],
        additional_outputs=[state, request_stats, session_stats],
    )

    clear_btn = gr.Button("🗑️ Clear Conversation")

    clear_btn.click(
        clear_conversation,
        outputs=[
            chat_interface.chatbot,
            state,
            request_stats,
            session_stats,
        ],
    )

if __name__ == "__main__":
    demo.launch()
