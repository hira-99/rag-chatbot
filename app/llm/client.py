"""Thin wrapper around the model API client used by every other module."""
from openai import (
    OpenAI,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    BadRequestError,
)

from app.config import OPENAI_API_KEY, MODEL_NAME

client = OpenAI(api_key=OPENAI_API_KEY)


def stream_chat_completion(messages):
    """Stream a chat completion, yielding text deltas as they arrive.

    On failure, yields a single readable error string and stops -- callers
    (the UI layer) don't need their own try/except around this generator.
    """
    if not OPENAI_API_KEY:
        yield "❌ OPENAI_API_KEY is missing."
        return

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    except AuthenticationError:
        yield "❌ Invalid or missing OpenAI API key."
    except RateLimitError:
        yield "⚠️ Rate limit exceeded. Please wait a moment and try again."
    except APIConnectionError:
        yield "\U0001f310 Unable to connect to OpenAI. Please check your internet connection."
    except APITimeoutError:
        yield "⌛ The request timed out. Please try again."
    except BadRequestError as e:
        yield f"❌ Invalid request: {e}"
    except Exception as e:
        yield f"❌ Unexpected error: {e}"


def generate_title(user_message, assistant_message):
    """A short conversation title from its first exchange. Not streamed --
    it's small and the caller needs the whole thing before saving it."""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short, specific conversation title (3-6 words). "
                        "No quotes, no trailing punctuation."
                    ),
                },
                {"role": "user", "content": f"User: {user_message}\nAssistant: {assistant_message}"},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "New conversation"
