"""Aggregate metrics computed from stored spans (Step 25.8): average/p95
response time, tool failure rate, retrieval hit rate, approval rejection
rate -- system health, not any one trace's detail (that's traces.py).
"""
import json

from app.database.connection import get_connection
from app.database.models import get_all_spans


def _percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct), len(ordered) - 1)
    return ordered[index]


def _chunk_count(span):
    if not span["output_summary"]:
        return 0
    try:
        return json.loads(span["output_summary"]).get("chunk_count", 0)
    except (ValueError, AttributeError):
        return 0


def compute_metrics(user_id):
    conn = get_connection()
    turn_spans = get_all_spans(conn, user_id, span_type="turn")
    tool_spans = get_all_spans(conn, user_id, span_type="tool_call")
    retrieval_spans = get_all_spans(conn, user_id, span_type="retrieval")
    conn.close()

    durations = [s["duration_ms"] for s in turn_spans if s["duration_ms"] is not None]

    tool_failures = sum(1 for s in tool_spans if s["status"] == "error")
    tool_failure_rate = tool_failures / len(tool_spans) if tool_spans else 0.0

    retrieval_hits = sum(1 for s in retrieval_spans if s["status"] == "ok" and _chunk_count(s) > 0)
    retrieval_hit_rate = retrieval_hits / len(retrieval_spans) if retrieval_spans else 0.0

    conn = get_connection()
    # Approval outcomes aren't spans (they're pending_approvals rows,
    # already the source of truth for E.6) -- reuse that table directly
    # rather than duplicating its status into trace_spans too.
    all_approvals = conn.execute(
        "SELECT status FROM pending_approvals WHERE user_id = ? AND status != 'pending'", (user_id,)
    ).fetchall()
    conn.close()
    rejected = sum(1 for a in all_approvals if a["status"] == "rejected")
    approval_rejection_rate = rejected / len(all_approvals) if all_approvals else 0.0

    return {
        "turn_count": len(turn_spans),
        "avg_response_ms": round(sum(durations) / len(durations), 1) if durations else 0.0,
        "p95_response_ms": round(_percentile(durations, 0.95), 1),
        "tool_call_count": len(tool_spans),
        "tool_failure_rate": round(tool_failure_rate, 3),
        "retrieval_count": len(retrieval_spans),
        "retrieval_hit_rate": round(retrieval_hit_rate, 3),
        "approval_count": len(all_approvals),
        "approval_rejection_rate": round(approval_rejection_rate, 3),
    }
