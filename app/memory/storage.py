"""Long-term memory and conversation-summary storage -- the orchestration
that ties extraction, conflict resolution, and consent together. Plain
view/edit/delete CRUD lives directly in app/database/models.py; this is
for the save and summarize paths, which have real decisions to make.
"""
import json

from app.database.connection import get_connection
from app.database.models import (
    get_conversation_summary,
    get_consent_mode,
    list_memories,
    save_conversation_summary,
    save_memory_row,
    supersede_memory,
)
from app.memory.conflicts import decide_action
from app.memory.permissions import default_scope_for_new_memory
from app.memory.short_term import split_recent_and_archived
from app.memory.summarizer import update_summary
from app.retrieval.embeddings import get_embedding


def save_extracted_memories(user_id, candidates, source_conversation_id):
    """candidates: a CandidateMemory list already passed through
    extraction.apply_saving_rules. Consent gates sensitive candidates;
    conflict resolution gates duplicates/contradictions. Returns how many
    were actually saved."""
    conn = get_connection()
    consent_mode = get_consent_mode(conn, user_id)
    if consent_mode == "disabled":
        conn.close()
        return 0

    existing = list_memories(conn, user_id)
    saved_count = 0

    for candidate in candidates:
        if candidate.sensitive:
            # Neither consent mode has a UI prompt to actually ask in this
            # stage (no per-memory approval flow exists yet) -- both
            # "always_ask" and "auto_save_non_sensitive" mean a sensitive
            # candidate does NOT get silently saved.
            continue

        embedding = get_embedding(candidate.text)
        embedding_json = json.dumps(embedding)
        action, matched = decide_action(embedding, existing)
        if action == "skip":
            continue

        memory_id = save_memory_row(
            conn, user_id, candidate.text, candidate.memory_type, embedding_json,
            scope=default_scope_for_new_memory(user_id),
            source_conversation_id=source_conversation_id, confidence=candidate.confidence,
        )
        if action == "supersede":
            supersede_memory(conn, matched["memory_id"], memory_id)

        existing.append({"memory_id": memory_id, "embedding": embedding_json})
        saved_count += 1

    conn.close()
    return saved_count


def maybe_update_summary(conversation_id, all_messages):
    """Folds any newly archived messages (short_term's sliding window)
    into the conversation's running summary. A no-op once the conversation
    is short enough that nothing has been archived yet."""
    _, archived = split_recent_and_archived(all_messages)

    conn = get_connection()
    existing = get_conversation_summary(conn, conversation_id)
    archived_through = existing["archived_through_count"] if existing else 0

    new_archived = archived[archived_through:]
    if not new_archived:
        conn.close()
        return

    updated_summary = update_summary(existing["summary_text"] if existing else "", new_archived)
    save_conversation_summary(conn, conversation_id, updated_summary, len(archived))
    conn.close()
