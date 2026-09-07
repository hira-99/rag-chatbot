"""Vector store client wrapper: add, query, delete."""
import chromadb

from app.config import CHROMA_HOST, CHROMA_PORT, VECTOR_COLLECTION_NAME
from app.retrieval.embeddings import get_embedding

_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
_collection = _client.get_or_create_collection(name=VECTOR_COLLECTION_NAME)


def add_chunk(chunk_id, text, metadata=None):
    """upsert, not add -- re-ingesting the same chunk_id (reseeding, a
    reindex that reuses ids) should replace it, not raise a duplicate-id
    error."""
    embedding = get_embedding(text)
    full_metadata = {**(metadata or {}), "is_active": True}
    _collection.upsert(ids=[chunk_id], documents=[text], embeddings=[embedding], metadatas=[full_metadata])


def set_active(chunk_id, is_active):
    """Soft-deactivate a chunk (C.5's reindex/supersede) without removing
    it -- Chroma's update() merges into existing metadata, it doesn't
    replace it, so this only touches the one field."""
    _collection.update(ids=[chunk_id], metadatas=[{"is_active": is_active}])


def query(query_text, top_k=10, where=None):
    embedding = get_embedding(query_text)
    active_filter = {"is_active": {"$eq": True}}
    combined_where = {"$and": [active_filter, where]} if where else active_filter
    kwargs = {"query_embeddings": [embedding], "n_results": top_k, "where": combined_where}
    raw = _collection.query(**kwargs)

    results = []
    if not raw["ids"][0]:
        return results
    for i, chunk_id in enumerate(raw["ids"][0]):
        results.append({
            "chunk_id": chunk_id,
            "text": raw["documents"][0][i],
            "metadata": raw["metadatas"][0][i] or {},
        })
    return results


def delete_chunk(chunk_id):
    _collection.delete(ids=[chunk_id])
