"""Lexical search client wrapper: index, search."""
from elasticsearch import Elasticsearch

from app.config import ELASTICSEARCH_URL, LEXICAL_INDEX_NAME

_es = Elasticsearch(ELASTICSEARCH_URL)


def ensure_index():
    if not _es.indices.exists(index=LEXICAL_INDEX_NAME):
        _es.indices.create(index=LEXICAL_INDEX_NAME, mappings={
            "properties": {
                "chunk_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "text": {"type": "text"},
                "title": {"type": "text"},
                "user_id": {"type": "keyword"},
                "is_active": {"type": "boolean"},
            }
        })


def index_chunk(chunk_id, text, metadata=None):
    ensure_index()
    doc = {"chunk_id": chunk_id, "text": text, "is_active": True, **(metadata or {})}
    _es.index(index=LEXICAL_INDEX_NAME, id=chunk_id, document=doc)


def set_active(chunk_id, is_active):
    """Soft-deactivate a chunk (C.5's reindex/supersede) -- a partial
    `doc` update merges into the existing document instead of replacing it."""
    ensure_index()
    _es.update(index=LEXICAL_INDEX_NAME, id=chunk_id, doc={"is_active": is_active})


def search(query_text, top_k=10, filters=None):
    ensure_index()
    filter_clauses = [{"term": {"is_active": True}}]
    filter_clauses += [{"term": {field: value}} for field, value in (filters or {}).items()]
    body = {
        "size": top_k,
        "query": {"bool": {"must": [{"match": {"text": query_text}}], "filter": filter_clauses}},
    }
    raw = _es.search(index=LEXICAL_INDEX_NAME, **body)

    results = []
    for hit in raw["hits"]["hits"]:
        source = hit["_source"]
        results.append({"chunk_id": source["chunk_id"], "text": source["text"], "metadata": source})
    return results


def delete_chunk(chunk_id):
    _es.options(ignore_status=[404]).delete(index=LEXICAL_INDEX_NAME, id=chunk_id)
