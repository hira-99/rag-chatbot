"""Context-dependent query rewriting into standalone queries."""
import re

from pydantic import BaseModel

from app.config import MODEL_NAME
from app.llm.client import client

PRONOUN_PATTERN = re.compile(
    r"\b(he|she|it|they|him|her|them|his|its|their|this|that|these|those)\b", re.IGNORECASE
)

REWRITE_SYSTEM_PROMPT = """Rewrite the user's latest message into a standalone search query, \
using the conversation to resolve any references (pronouns, "that policy", "the same thing").

The rewritten query MUST:
- Preserve all names, dates, and identifiers exactly as given.
- Preserve the requested scope -- if the user narrowed or changed topic, reflect the NEW scope.
- Never answer the question -- output a search phrase, not a fact.
- Never add assumptions not stated in the conversation.
"""


class QueryRewrite(BaseModel):
    standalone_query: str


def looks_context_dependent(message):
    """Cheap pre-check so a rewrite call only happens when the message
    actually contains something that needs resolving against history."""
    return bool(PRONOUN_PATTERN.search(message))


def rewrite_query(conversation_history, latest_message):
    if not conversation_history or not looks_context_dependent(latest_message):
        return latest_message

    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_history)
    response = client.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Conversation:\n{history_text}\n\nLatest message: {latest_message}"},
        ],
        response_format=QueryRewrite,
    )
    return response.choices[0].message.parsed.standalone_query
