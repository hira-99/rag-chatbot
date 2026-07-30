import gradio as gr
from chatbot import chat 

def create_initial_state():
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are an Assistant."
            }
        ],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0,
        }
    }

with gr.Blocks() as demo:

    state = gr.State(create_initial_state())

    request_stats = gr.Markdown(
        """
        ### Current Request

        **Tokens**

        - Input: **0**
        - Output: **0**
        - Total: **0**

        **Cost**

        - Input: **$0.000000**
        - Output: **$0.000000**
        - Total: **$0.000000**
        """
    )


    session_stats = gr.Markdown(
        """
        ### Session

        **Tokens**

        - Input: **0**
        - Output: **0**
        - Total: **0**

        **Cost**

        - Total: **$0.000000**
        """
    )

    # clear_btn = gr.Button("🗑️ Clear Conversation")
    gr.ChatInterface(
        fn=chat, 
        title="Framework Free Chatbot",
        description="My first chatbot :p",
        additional_inputs=[state],
        additional_outputs=[state,request_stats,session_stats]
    )
demo.launch()



### -------------- DUMMY ----------
# for understanding how the chatbot is actually working

# def chatbot(message, history):
#     return "THIS IS A DUMMY RESPONSE, CHATBOT ISNT CONNECTED YET."

# with gr.Blocks(title="AI CHATBOT") as demo:
#     gr.Markdown("# 🤖 Framework-Free AI Chatbot")

#     chatbot_ui= gr.Chatbot(label="converstaion", height= 450)

#     with gr.Row():
#         msg= gr.Textbox(
#             placeholder="Your thoughts....",
#             show_label=False,
#             scale=8
#         )
#         send= gr.Button("Send", scale=1)

#     clear= gr.Button("Clear converstation")

#     gr.Markdown("### Usage")

#     token_usage = gr.Markdown("**Tokens Used:** 0")
#     cost_usage = gr.Markdown("**Estimated Cost:** $0.0000")

#     def respond(message, history):
#         if history is None:
#             history = []

#         reply = chat(message)

#         history.append(
#             {"role": "user", "content": message}
#         )
#         history.append(
#             {"role": "assistant", "content": reply}
#         )

#         # Dummy values for now
#         tokens = 0
#         cost = "$0.0000"

#         return (
#             history,
#             "",
#             f"**Tokens Used:** {tokens}",
#             f"**Estimated Cost:** {cost}",
#         )

#     send.click(
#         respond,
#         inputs=[msg, chatbot_ui],
#         outputs=[chatbot_ui, msg, token_usage, cost_usage],
#     )

#     msg.submit(
#         respond,
#         inputs=[msg, chatbot_ui],
#         outputs=[chatbot_ui, msg, token_usage, cost_usage],
#     )

#     clear.click(
#         lambda: ([], "**Tokens Used:** 0", "**Estimated Cost:** $0.0000"),
#         outputs=[chatbot_ui, token_usage, cost_usage],
#     )

# demo.launch() 
#-----------------------------------