"""Fixed-workflow vs. agentic-decision routing (E.5).

Most turns need neither -- Section D's router already retrieves documents
automatically. This decides the remaining question: does *this* turn need
a tool the router doesn't cover, and if so, is it simple/deterministic
enough to skip letting the model decide step by step?

A customer lookup by ID is the illustrative fixed workflow: parsing the ID
and calling the one tool it needs is deterministic, so routing it through
the full agent loop would just add model-decision variance with no
benefit. Anything else that needs a tool (arithmetic, current time, or a
customer question mixed with other reasoning) goes through the agent loop,
which lets the model decide what to call and in what order.
"""
import re

CUSTOMER_ID_PATTERN = re.compile(r"\bCUST-\d+\b", re.IGNORECASE)
MATH_PATTERN = re.compile(r"\d+\s*[+\-*/x×]\s*\d+|\bcalculate\b|\bcompute\b", re.IGNORECASE)
TIME_PATTERN = re.compile(
    r"\bwhat(?:'s| is) (?:the )?(?:current )?(?:date|time)\b|\btoday'?s date\b|\bcurrent time\b",
    re.IGNORECASE,
)


def route_turn(message):
    """Returns ("fixed_workflow", customer_id), ("agentic", None), or
    ("plain", None)."""
    customer_id_match = CUSTOMER_ID_PATTERN.search(message)
    if customer_id_match and len(message.split()) <= 8:
        return "fixed_workflow", customer_id_match.group(0).upper()

    if customer_id_match or MATH_PATTERN.search(message) or TIME_PATTERN.search(message):
        return "agentic", None

    return "plain", None
