"""Context budget enforcement and priority-based trimming."""
from app.llm.token_counter import count_tokens

MAX_CONTEXT_TOKENS = 8000
RESERVED_OUTPUT_TOKENS = 1000
AVAILABLE_INPUT_TOKENS = MAX_CONTEXT_TOKENS - RESERVED_OUTPUT_TOKENS

# Highest priority first -- matches the roadmap's explicit ordering (system
# and safety instructions first, then required tool results, retrieved
# evidence, recent messages, long-term memory, older summary last). The
# current user message effectively lives inside `recent_messages` (it's
# always the last entry by the time assemble_context is called), so there's
# no separate slot for it here.
CONTEXT_PRIORITY = [
    "system_instructions",
    "tool_results",
    "retrieved_evidence",
    "recent_messages",
    "long_term_memories",
    "conversation_summary",
]


def fit_to_budget(components, budget=AVAILABLE_INPUT_TOKENS):
    """Keep components in priority order until the budget runs out.

    `components` is {name: text}. Returns (kept, dropped) -- `dropped` is
    just the list of component names that didn't fit, so the caller can log
    what got trimmed (the roadmap's explicit "log what was removed").
    """
    kept = {}
    dropped = []
    remaining = budget

    for name in CONTEXT_PRIORITY:
        text = components.get(name) or ""
        tokens = count_tokens(text)
        if tokens <= remaining:
            kept[name] = text
            remaining -= tokens
        else:
            dropped.append(name)

    return kept, dropped
