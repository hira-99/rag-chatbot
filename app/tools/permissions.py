"""Per-user tool access filtering.

Real filtering logic, exercised even though there's currently one real user
(DEFAULT_USER_ID) -- see CLAUDE.md's multi-user scope note. Every user gets
every registered tool for now; the seam is here so a future role/permission
table only has to change this function, not every call site that needs to
know what a user is allowed to do.
"""
from app.tools.registry import TOOL_REGISTRY


def allowed_tool_names(user_id):
    return set(TOOL_REGISTRY.keys())
