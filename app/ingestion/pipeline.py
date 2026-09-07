"""Upload pipeline: load -> clean -> chunk -> embed -> index.

Runs inside the ingestion worker's thread pool (app/workers/ingestion_worker.py)
so the chat UI stays responsive while a file is processed.
"""
from pathlib import Path

from app.ingestion.chunkers import chunk_text
from app.ingestion.cleaners import clean_text
from app.ingestion.loaders.html_loader import load_html
from app.ingestion.loaders.markdown_loader import load_markdown
from app.ingestion.loaders.pdf_loader import load_pdf
from app.ingestion.loaders.text_loader import load_text
from app.retrieval import lexical_search, vector_store

LOADERS_BY_EXTENSION = {
    ".txt": load_text,
    ".md": load_markdown,
    ".html": load_html,
    ".htm": load_html,
    ".pdf": load_pdf,
}


def load_document(file_path):
    extension = Path(file_path).suffix.lower()
    loader = LOADERS_BY_EXTENSION.get(extension)
    if loader is None:
        raise ValueError(f"Unsupported file type: {extension}")
    return loader(file_path)


def ingest_file(file_path, attachment_id, title, user_id, on_stage=None):
    """Runs the full pipeline for one file, indexing its chunks into both
    retrieval stores tagged with document_id=attachment_id so they're
    filterable and deletable later (app/ui/files.py, app/database/models.py).
    Returns the number of chunks created.
    """
    def stage(name):
        if on_stage:
            on_stage(name)

    stage("extracting")
    raw_text = load_document(file_path)
    cleaned_text = clean_text(raw_text)

    stage("chunking")
    text_chunks = chunk_text(cleaned_text)
    chunk_ids = [f"{attachment_id}-{i}" for i in range(len(text_chunks))]
    metadata = {"document_id": attachment_id, "title": title, "user_id": user_id}

    stage("embedding")
    for chunk_id, chunk in zip(chunk_ids, text_chunks):
        vector_store.add_chunk(chunk_id, chunk, metadata)

    stage("indexing")
    for chunk_id, chunk in zip(chunk_ids, text_chunks):
        lexical_search.index_chunk(chunk_id, chunk, metadata)

    return len(text_chunks)


def deactivate_document_chunks(attachment_id, chunk_count):
    """C.5: supersede, not delete -- old chunks stop being retrieved from
    but stay in both stores for audit."""
    for i in range(chunk_count):
        chunk_id = f"{attachment_id}-{i}"
        vector_store.set_active(chunk_id, False)
        lexical_search.set_active(chunk_id, False)


def delete_document_chunks(attachment_id, chunk_count):
    """C.6: explicit user deletion -- hard delete from both stores."""
    for i in range(chunk_count):
        chunk_id = f"{attachment_id}-{i}"
        vector_store.delete_chunk(chunk_id)
        lexical_search.delete_chunk(chunk_id)
