"""File upload UI: upload handler, status list (polled), delete."""
import mimetypes
import uuid
from pathlib import Path

import gradio as gr

from app.config import DEFAULT_USER_ID
from app.database.connection import get_connection
from app.database.models import (
    create_attachment,
    delete_attachment,
    find_active_attachment_by_filename,
    get_attachment,
    list_attachments,
    supersede_attachment,
)
from app.ingestion.metadata import content_hash
from app.ingestion.pipeline import deactivate_document_chunks, delete_document_chunks
from app.workers.ingestion_worker import submit_ingestion_job


def refresh_file_choices(selected_attachment_id=None):
    """Same choices-vs-value shape as refresh_conversation_choices (A.3) --
    a bare list here would set the Radio's *value*, not its choices."""
    conn = get_connection()
    attachments = list_attachments(conn, DEFAULT_USER_ID)
    conn.close()
    choices = [(f"{a['filename']} -- {a['status']}", a["attachment_id"]) for a in attachments]
    return gr.update(choices=choices, value=selected_attachment_id)


def upload_file(file_path):
    """Handles a gr.File upload: hash + persist the attachment row, supersede
    any previous active version of the same filename (C.5), and hand the
    actual load/chunk/embed/index work to the background worker so this
    returns immediately -- the chat UI never blocks on ingestion.
    """
    if not file_path:
        return refresh_file_choices()

    path = Path(file_path)
    raw_bytes = path.read_bytes()
    file_hash = content_hash(raw_bytes)

    conn = get_connection()
    existing = find_active_attachment_by_filename(conn, DEFAULT_USER_ID, path.name)
    if existing:
        if existing["content_hash"] == file_hash:
            # Byte-identical re-upload -- nothing changed, no-op.
            conn.close()
            return refresh_file_choices(selected_attachment_id=existing["attachment_id"])
        supersede_attachment(conn, existing["attachment_id"])
        deactivate_document_chunks(existing["attachment_id"], existing["chunk_count"])

    attachment_id = uuid.uuid4().hex
    mime_type = mimetypes.guess_type(path.name)[0]
    create_attachment(conn, attachment_id, DEFAULT_USER_ID, path.name, mime_type, len(raw_bytes), file_hash)
    conn.close()

    submit_ingestion_job(str(path), attachment_id, path.name, DEFAULT_USER_ID)
    return refresh_file_choices(selected_attachment_id=attachment_id)


def do_delete_file(attachment_id):
    """C.6: hard delete -- removes the row and its chunks from both
    retrieval stores, scoped to this attachment only."""
    if attachment_id:
        conn = get_connection()
        attachment = get_attachment(conn, attachment_id)
        if attachment:
            delete_document_chunks(attachment_id, attachment["chunk_count"])
            delete_attachment(conn, attachment_id)
        conn.close()
    return refresh_file_choices()
