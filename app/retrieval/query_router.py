"""Decide no-retrieval / vector / lexical / hybrid / clarification."""
import re
from typing import Literal

from pydantic import BaseModel

from app.config import MODEL_NAME
from app.llm.client import client

GREETING_PATTERN = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|good morning|good evening)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"\b[A-Z]{2,}-\d+\b")


def _rule_based_route(query_text):
    """Cheap, deterministic checks tried before spending a model call --
    same rule-first order proven in Step 11's notebook router."""
    stripped = query_text.strip()
    if not stripped:
        return "clarification_needed"
    if GREETING_PATTERN.match(stripped):
        return "no_retrieval"
    if IDENTIFIER_PATTERN.search(stripped):
        return "lexical"
    return None


class RouteDecision(BaseModel):
    route: Literal["no_retrieval", "vector", "lexical", "hybrid", "clarification_needed"]
    reason: str


ROUTER_SYSTEM_PROMPT = """Classify the query into exactly one retrieval route.

- no_retrieval = small talk, or a question answerable from general knowledge \
that has nothing to do with ByteMage (the company these documents cover).
- lexical = looking for an exact term, code, or name.
- vector = an open-ended question about ByteMage policy, product, or process \
-- "what is...", "how many...", "explain...", "what's the process for...". \
This is the default for any ByteMage-specific factual question, even a short one.
- hybrid = a ByteMage question that also names a specific term, code, or identifier.
- clarification_needed = ONLY when the query is so vague there is nothing to \
search for at all (e.g. a single word like "policy", or "tell me about it" \
with no prior context). A question that already names a clear topic (PTO, \
leave, compensation, onboarding, etc.) is NEVER clarification_needed, even \
if it doesn't specify company/role/region -- assume it means ByteMage.

Examples:
"How many days of PTO do employees get?" -> vector
"What is the PTO policy?" -> vector
"hi there" -> no_retrieval
"What's 12 * 4?" -> no_retrieval
"policy" -> clarification_needed
"""


def _model_based_route(query_text):
    response = client.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ],
        response_format=RouteDecision,
    )
    return response.choices[0].message.parsed


def route_query(query_text):
    route = _rule_based_route(query_text)
    if route is not None:
        return {"route": route, "method": "rule"}
    decision = _model_based_route(query_text)
    return {"route": decision.route, "method": "model", "reason": decision.reason}
