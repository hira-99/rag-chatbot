"""Structured JSON event logging -- every span is stored as one redacted
row (app/database's trace_spans table), not printed to a log file.
"""
import json
import uuid
from datetime import datetime, timezone

from app.database.connection import get_connection
from app.database.models import save_trace_span
from app.observability.redaction import redact


def new_trace_id():
    return uuid.uuid4().hex


def _now():
    return datetime.now(timezone.utc).isoformat()


def _summarize(data):
    if data is None:
        return None
    return redact(json.dumps(data, default=str)[:2000])


def log_span(trace_id, parent_span_id, user_id, conversation_id, span_type, name,
             input_data=None, output_data=None, status="ok", error_category=None,
             duration_ms=None, cost_usd=None):
    span_id = uuid.uuid4().hex
    conn = get_connection()
    save_trace_span(
        conn, span_id, trace_id, parent_span_id, user_id, conversation_id, span_type, name,
        _summarize(input_data), _summarize(output_data), status, error_category, duration_ms, cost_usd, _now(),
    )
    conn.close()
    return span_id
