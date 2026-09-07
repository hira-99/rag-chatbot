"""Sensitive-data redaction applied before any event is stored (Step 25.9).

Called from app/observability/logging.py before a span is persisted --
every event gets redacted before storage, not after.
"""
import re

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # OpenAI-style API keys
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE),  # bearer tokens
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-shaped
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # credit-card-shaped digit runs
]


def redact(text):
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
