"""Relevance-thresholded long-term memory retrieval.

A plain SQLite table plus a Python cosine-similarity loop -- Step 14's own
simplification: memories are few enough per user that running a vector
database for them would be pure overhead.
"""
import json
import math

from app.database.connection import get_connection
from app.database.models import list_memories_for_retrieval
from app.retrieval.embeddings import get_embedding


# text-embedding-3-small cosine similarities run much lower than intuition
# suggests -- confirmed live: a genuinely relevant memory-to-query pair
# scored 0.37-0.66, while unrelated pairs stayed under 0.17. 0.75 (a
# plausible-looking first guess) silenced retrieval almost entirely.
RELEVANCE_THRESHOLD = 0.3
MAX_MEMORIES = 5


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_relevant_memories(user_id, query_text):
    conn = get_connection()
    memories = list_memories_for_retrieval(conn, user_id)
    conn.close()
    if not memories:
        return []

    query_embedding = get_embedding(query_text)
    scored = []
    for memory in memories:
        similarity = cosine_similarity(query_embedding, json.loads(memory["embedding"]))
        if similarity >= RELEVANCE_THRESHOLD:
            scored.append({**memory, "similarity": similarity})

    # Skip retrieval entirely rather than injecting a merely-closest match
    # (Step 14.7) -- the threshold above already does this; sorting just
    # orders what passed it.
    scored.sort(key=lambda m: m["similarity"], reverse=True)
    return scored[:MAX_MEMORIES]
