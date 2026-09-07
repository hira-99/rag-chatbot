"""In-process thread pool for file ingestion.

Keeps the upload handler responsive -- the chat UI doesn't block while a
file is loaded/chunked/embedded/indexed. No new service (Redis, Celery):
just a ThreadPoolExecutor, per the scope decision for this project.
"""
from concurrent.futures import ThreadPoolExecutor

from app.database.connection import get_connection
from app.database.models import update_attachment_status
from app.ingestion.pipeline import ingest_file

_executor = ThreadPoolExecutor(max_workers=2)


def submit_ingestion_job(file_path, attachment_id, filename, user_id):
    _executor.submit(_run_ingestion, file_path, attachment_id, filename, user_id)


def _run_ingestion(file_path, attachment_id, filename, user_id):
    conn = get_connection()
    try:
        chunk_count = ingest_file(
            file_path, attachment_id, filename, user_id,
            on_stage=lambda stage: update_attachment_status(conn, attachment_id, stage),
        )
        update_attachment_status(conn, attachment_id, "ready", chunk_count=chunk_count)
    except Exception as exc:
        update_attachment_status(conn, attachment_id, "failed", error_message=str(exc))
    finally:
        conn.close()
