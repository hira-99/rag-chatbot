"""Application entry point -- wires everything together and launches the UI."""
import gradio as gr

from app.ui.chat import respond

demo = gr.ChatInterface(
    fn=respond,
    title="ChatBot Assistant",
    description="Phase 8 capstone -- Stage A.1: streaming chat.",
)

if __name__ == "__main__":
    demo.launch()
