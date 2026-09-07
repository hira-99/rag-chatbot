"""Knowledge-base search tool, wraps retrieval.hybrid_search.

Lets the agent loop search documents itself when it decides it needs to
(Step 21's "RAG as an agent tool") -- distinct from Section D's router,
which retrieves automatically before every plain-streaming turn without
the model asking for it.
"""
from pydantic import BaseModel, Field

from app.retrieval.citations import assign_source_numbers
from app.retrieval.hybrid_search import hybrid_search
from app.retrieval.reranker import rerank


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="A search query for ByteMage's internal documents")


def search_knowledge_base(query: str):
    candidates = hybrid_search(query, top_k=10)
    chunks = rerank(query, candidates, keep_top_n=5)
    sources = assign_source_numbers(chunks)
    return {
        "query": query,
        "results": [{"number": s["number"], "title": s["title"], "text": s["text"]} for s in sources],
    }
