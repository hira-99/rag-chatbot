"""Extract candidate long-term memories from a conversation turn, then
apply deterministic saving rules (Step 14.3-14.4) before anything is
actually stored -- extraction decides what MIGHT matter, the rules decide
what's actually worth keeping.
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.config import MODEL_NAME
from app.llm.client import client

MemoryType = Literal["preference", "personal_fact", "project_fact", "decision"]


class CandidateMemory(BaseModel):
    text: str
    memory_type: MemoryType
    confidence: float = Field(ge=0, le=1)
    sensitive: bool = Field(description="True if this touches health, finances, or other sensitive personal data")


class ExtractionResult(BaseModel):
    memories: list[CandidateMemory]


EXTRACTION_SYSTEM_PROMPT = """Identify any facts, preferences, or decisions from this exchange
that would be useful to remember in a FUTURE conversation -- not just this one.
Skip greetings, one-time requests, and anything already obvious or generic.
Only include something if you're reasonably confident it's a durable fact about
the user or their ongoing work, not a one-off detail. Return an empty list if
nothing qualifies."""

MIN_CONFIDENCE = 0.6


def extract_candidates(user_message, assistant_message):
    response = client.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"User: {user_message}\nAssistant: {assistant_message}"},
        ],
        response_format=ExtractionResult,
    )
    return response.choices[0].message.parsed.memories


def apply_saving_rules(candidates):
    """The actual gate -- extraction can be enthusiastic; a confidence
    threshold is the deterministic filter (Step 14.4). Consent for
    sensitive candidates is enforced separately, by storage.py, since it
    needs the user's consent_mode setting."""
    return [c for c in candidates if c.confidence >= MIN_CONFIDENCE]
