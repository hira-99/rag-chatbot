"""Wraps one operation as a traced span: times it, catches and categorizes
errors, and logs it (app/observability/logging.py) once it finishes.

Three call sites use this (Step 25.3-25.5): the model call and retrieval
in app/ui/chat.py, and each tool call inside app/agent/loop.py -- thin
wrappers around code already built in Sections B/D/E, not new logic.
"""
import time
from contextlib import contextmanager

from app.observability.logging import log_span

ERROR_CATEGORIES = {
    "validation_error", "permission_denied", "timeout", "rate_limit",
    "not_found", "external_service_error", "model_error", "retrieval_error",
    "user_cancelled",
}

_DEFAULT_ERROR_CATEGORY = {
    "model_call": "model_error",
    "retrieval": "retrieval_error",
    "tool_call": "external_service_error",
}


@contextmanager
def traced_span(trace_id, parent_span_id, user_id, conversation_id, span_type, name, input_data=None):
    """Usage:
        with traced_span(trace_id, None, user_id, conv_id, "retrieval", "hybrid_search", input_data={...}) as span:
            result = do_the_thing()
            span["output"] = {"chunk_count": len(result)}
    `span` is a plain dict the caller fills in -- whatever's in it at the
    end (or at the point an exception is raised) becomes the span's
    output_summary.
    """
    start = time.perf_counter()
    span = {}
    status = "ok"
    error_category = None
    try:
        yield span
    except GeneratorExit:
        # The enclosing generator (e.g. bot_respond) was cancelled --
        # Gradio's cancels= (A.6) raises this. Record it as its own
        # category (Step 25.6) instead of letting it look like an
        # ordinary success or a generic error, then propagate it as
        # required (a context manager must not swallow GeneratorExit).
        status = "error"
        error_category = "user_cancelled"
        raise
    except Exception as exc:
        status = "error"
        error_category = _DEFAULT_ERROR_CATEGORY.get(span_type, "external_service_error")
        span["error"] = str(exc)
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_span(
            trace_id, parent_span_id, user_id, conversation_id, span_type, name,
            input_data=input_data, output_data=span or None,
            status=status, error_category=error_category, duration_ms=duration_ms,
        )
