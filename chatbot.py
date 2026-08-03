from openai import OpenAI
from state import create_initial_state
from config import OPENAI_API_KEY,MODEL_NAME
from pprint import pprint
from helperFunctions import calculate_cost
from openai import (
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    BadRequestError,
)

client= OpenAI(api_key=OPENAI_API_KEY)

def get_request_stats(
    input_tokens=0,
    output_tokens=0,
    total_tokens=0,
    cost=None,
):
    if cost is None:
        cost = {
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
        }

    return f"""
            ### Current Request

            **Tokens**

            - Input: **{input_tokens}**
            - Output: **{output_tokens}**
            - Total: **{total_tokens}**

            **Cost**

            - Input: **${cost['input_cost']:.6f}**
            - Output: **${cost['output_cost']:.6f}**
            - Total: **${cost['total_cost']:.6f}**
            """

def get_session_stats(usage):
    return f"""
            ### Session

            **Tokens**

            - Input: **{usage['input_tokens']}**
            - Output: **{usage['output_tokens']}**
            - Total: **{usage['total_tokens']}**

            **Cost**

            - Total: **${usage['total_cost']:.6f}**
            """

def clear_conversation():
    state = create_initial_state()

    request_stats = get_request_stats()

    session_stats = get_session_stats(state["usage"])

    return [], state, request_stats, session_stats

# state -> openai messages stored in state
# ui_history -> chatInterface 
# latest_message -> latest user message 

def chat(latest_message, ui_history, state):

    messages = state["messages"]
    usage = state["usage"] 

     # Missing API key
    if not OPENAI_API_KEY:
        return (
            "❌ OPENAI_API_KEY is missing.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )
    
  # Empty message
    if not latest_message.strip():
        return (
            "⚠️ Please enter a message before sending.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

# Add user message
    messages.append(
        {
            "role": "user",
            "content": latest_message
        }
    )

    try:
        response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages
    )

        assistant_reply= response.choices[0].message.content

        # Save assistant response
        messages.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
        )

        # ----- show the token count
        # Current request usage
        input_tokens= response.usage.prompt_tokens
        output_tokens=response.usage.completion_tokens
        total_tokens= response.usage.total_tokens

        cost = calculate_cost(
                MODEL_NAME,
                input_tokens,
                output_tokens
            )

        # Session totals
        usage["input_tokens"] += input_tokens
        usage["output_tokens"] += output_tokens
        usage["total_tokens"] += total_tokens
        usage["total_cost"] += cost["total_cost"]

        request_stats = get_request_stats(
            input_tokens,
            output_tokens,
            total_tokens,
            cost,
        )

        session_stats = get_session_stats(usage)

        return (
            assistant_reply,
            state,
            request_stats,
            session_stats,
        )
    
    # print("\nConversation History:")
    # pprint(messages)

    except AuthenticationError:
        return (
            "❌ Invalid or missing OpenAI API key.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

    except RateLimitError:
        return (
            "⚠️ Rate limit exceeded. Please wait a moment and try again.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

    except APIConnectionError:
        return (
            "🌐 Unable to connect to OpenAI. Please check your internet connection.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

    except APITimeoutError:
        return (
            "⌛ The request timed out. Please try again.",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

    except BadRequestError as e:
        return (
            f"❌ Invalid request: {e}",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )

    except Exception as e:
        return (
            f"❌ Unexpected error: {e}",
            state,
            get_request_stats(),
            get_session_stats(usage),
        )
