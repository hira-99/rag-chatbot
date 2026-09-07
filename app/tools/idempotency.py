"""Idempotency keys for tool calls.

Lets a regenerate (A.4) or a resumed approval run reuse a prior tool
result instead of re-executing it -- a sensitive action (or an expensive
one) should never run twice for what is logically the same request.
"""
import hashlib
import json


def make_idempotency_key(user_id, tool_name, arguments, run_id):
    payload = json.dumps(
        {"user_id": user_id, "tool": tool_name, "arguments": arguments, "run_id": run_id},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
