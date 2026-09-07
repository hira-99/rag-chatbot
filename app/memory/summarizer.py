"""Incremental conversation summarization (Step 13.5-13.6): update the
existing summary with newly archived messages instead of resummarizing
the whole conversation from scratch every time.
"""
from app.config import MODEL_NAME
from app.llm.client import client

SUMMARIZER_SYSTEM_PROMPT = """Update the running summary of this conversation with the new messages.

Preserve durable facts: the user's stated goal, decisions made, numbers/dates
mentioned, preferences, and anything explicitly rejected. Keep it concise --
a few sentences, not a transcript. If a new message contradicts something in
the existing summary, keep only the newer fact."""


def update_summary(existing_summary, archived_messages):
    if not archived_messages:
        return existing_summary

    archived_text = "\n".join(f"{m['role']}: {m['content']}" for m in archived_messages)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Existing summary:\n{existing_summary or '(none yet)'}\n\nNew messages:\n{archived_text}"},
        ],
    )
    return response.choices[0].message.content.strip()
