"""Trace viewer: developer-facing, kept separate from the user-facing chat
(roadmap's explicit requirement -- wired into its own tab in main.py, not
mixed into the chat pane). Shows a timeline of spans per trace and the
aggregate metrics from app/observability/metrics.py.
"""
import gradio as gr

from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import get_trace_spans, list_recent_traces
from app.observability.metrics import compute_metrics


def refresh_trace_choices(selected_trace_id=None):
    conn = get_connection()
    traces = list_recent_traces(conn, DEFAULT_USER_ID, limit=30)
    conn.close()
    choices = [
        (f"{t['started_at'][:19]} -- {t['name']} ({t['status']}, {round(t['duration_ms'] or 0)}ms)", t["trace_id"])
        for t in traces
    ]
    return gr.update(choices=choices, value=selected_trace_id)


def load_trace_timeline(trace_id):
    if not trace_id:
        return "Select a trace to see its spans."

    conn = get_connection()
    spans = get_trace_spans(conn, trace_id)
    conn.close()

    lines = []
    for span in spans:
        marker = "🔴" if span["status"] == "error" else "🟢"
        duration = f"{round(span['duration_ms'])}ms" if span["duration_ms"] is not None else "?"
        lines.append(f"{marker} [{span['span_type']}] {span['name']} -- {duration}")
        if span["input_summary"]:
            lines.append(f"    in:  {span['input_summary']}")
        if span["output_summary"]:
            lines.append(f"    out: {span['output_summary']}")
        if span["error_category"]:
            lines.append(f"    error_category: {span['error_category']}")
        lines.append("")
    return "\n".join(lines) if lines else "No spans recorded for this trace."


def load_metrics_summary():
    metrics = compute_metrics(DEFAULT_USER_ID)
    return (
        f"Turns: {metrics['turn_count']}  |  "
        f"Avg response: {metrics['avg_response_ms']}ms  |  "
        f"P95 response: {metrics['p95_response_ms']}ms\n"
        f"Tool calls: {metrics['tool_call_count']}  |  "
        f"Tool failure rate: {metrics['tool_failure_rate']:.0%}\n"
        f"Retrievals: {metrics['retrieval_count']}  |  "
        f"Retrieval hit rate: {metrics['retrieval_hit_rate']:.0%}\n"
        f"Approvals: {metrics['approval_count']}  |  "
        f"Approval rejection rate: {metrics['approval_rejection_rate']:.0%}"
    )
