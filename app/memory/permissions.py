"""Memory scope isolation -- personal (only the owning user) vs org
(every user). Real filtering logic exercised even with one real user (see
CLAUDE.md's multi-user scope note): app/database/models.py's
list_memories_for_retrieval already applies this at the query level; this
is the seam a future role/org model would extend without changing every
call site.
"""


def default_scope_for_new_memory(user_id):
    return "personal"
