"""Agent run state.

Deliberately minimal -- messages, step count, status, and the set of
tool-call signatures already made this run (for repetition detection).
A production agent would also track token usage and cost per step
(app/observability/cost.py's job, a later stage); this is what the loop
itself needs to make its next decision.
"""
from dataclasses import dataclass, field


@dataclass
class AgentState:
    run_id: str
    conversation_id: str
    user_id: str
    messages: list
    step: int = 0
    status: str = "running"  # running | done | awaiting_approval | failed
    seen_tool_calls: set = field(default_factory=set)
