"""Combines vector_store and lexical_search results, and orchestrates the
full retrieval flow (rewrite -> route -> search -> rerank) for a chat turn.
"""
from app.retrieval import lexical_search, vector_store
from app.retrieval.query_router import route_query
from app.retrieval.query_rewriter import rewrite_query
from app.retrieval.rank_fusion import reciprocal_rank_fusion
from app.retrieval.reranker import rerank


def _to_chroma_where(filters):
    if not filters:
        return None
    clauses = [{field: {"$eq": value}} for field, value in filters.items()]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def hybrid_search(query_text, top_k=10, filters=None):
    vector_results = vector_store.query(query_text, top_k=top_k, where=_to_chroma_where(filters))
    lexical_results = lexical_search.search(query_text, top_k=top_k, filters=filters)
    fused = reciprocal_rank_fusion({"vector": vector_results, "bm25": lexical_results})
    return fused[:top_k]


def retrieve_for_query(latest_message, conversation_history=None, top_k=10, keep_top_n=5, filters=None):
    """The single entry point bot_respond calls: resolves references,
    decides whether/how to search, and returns a short reranked list of
    chunks (or an empty list when no retrieval is needed).
    """
    standalone_query = rewrite_query(conversation_history or [], latest_message)
    decision = route_query(standalone_query)
    route = decision["route"]

    if route in ("no_retrieval", "clarification_needed"):
        return {"chunks": [], "route": route, "query": standalone_query}

    if route == "vector":
        candidates = vector_store.query(standalone_query, top_k=top_k, where=_to_chroma_where(filters))
    elif route == "lexical":
        candidates = lexical_search.search(standalone_query, top_k=top_k, filters=filters)
    else:  # hybrid
        candidates = hybrid_search(standalone_query, top_k=top_k, filters=filters)

    chunks = rerank(standalone_query, candidates, keep_top_n=keep_top_n)
    return {"chunks": chunks, "route": route, "query": standalone_query}
