"""Cost limits and per-user/per-day budget enforcement (Step 25.10): stop
giving a user new turns once they've exceeded the daily cap, rather than
just recording usage after the fact.

Agent step/model-call limits already exist and are enforced elsewhere
(app/agent/limits.MAX_STEPS caps one turn's tool-calling rounds) -- this
covers the per-user-per-day case, which nothing else tracks.
"""
from datetime import datetime, timezone

from app.config import MODEL_NAME
from app.database.connection import get_connection
from app.llm.pricing import estimate_cost

MAX_COST_PER_DAY_USD = 1.00
MAX_MESSAGES_PER_DAY = 200


def _today_start_iso():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def get_daily_usage(user_id):
    """Approximates cost from each message's stored token_count -- the app
    doesn't track separate input/output tokens per model call (a user
    message's context includes system instructions, summary, retrieved
    evidence, and history, not just its own text), so this treats a user
    message's tokens as input and an assistant message's tokens as output
    for that exchange. A soft daily cap, not exact billing.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, token_count FROM messages WHERE user_id = ? AND created_at >= ? AND token_count IS NOT NULL",
        (user_id, _today_start_iso()),
    ).fetchall()
    conn.close()

    total_cost = 0.0
    for row in rows:
        if row["role"] == "user":
            total_cost += estimate_cost(MODEL_NAME, input_tokens=row["token_count"])
        elif row["role"] == "assistant":
            total_cost += estimate_cost(MODEL_NAME, output_tokens=row["token_count"])

    return {"message_count": len(rows), "estimated_cost_usd": round(total_cost, 4)}


def check_within_limits(user_id):
    """Returns (allowed, reason) -- reason is None when allowed."""
    usage = get_daily_usage(user_id)
    if usage["message_count"] >= MAX_MESSAGES_PER_DAY:
        return False, f"Daily message limit reached ({MAX_MESSAGES_PER_DAY} messages). Try again tomorrow."
    if usage["estimated_cost_usd"] >= MAX_COST_PER_DAY_USD:
        return False, f"Daily usage limit reached (${MAX_COST_PER_DAY_USD:.2f} estimated). Try again tomorrow."
    return True, None
