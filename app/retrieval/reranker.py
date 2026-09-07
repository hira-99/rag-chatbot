"""Second-stage candidate reranking.

Step 8's notebook left this as an unimplemented learner exercise -- the app
needs a working one, so this is new work rather than a port: a single batched
LLM call that scores every candidate's relevance to the query, 0-10.
"""
from pydantic import BaseModel, Field

from app.config import MODEL_NAME
from app.llm.client import client


class ChunkScore(BaseModel):
    chunk_id: str
    relevance_score: int = Field(ge=0, le=10)


class BatchRerankResult(BaseModel):
    scores: list[ChunkScore]


def rerank(query, candidates, keep_top_n=5):
    if not candidates:
        return []

    candidates_block = "\n".join(f"[{c['chunk_id']}] {c['text'][:300]}" for c in candidates)
    response = client.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": (
                "Score how well each chunk answers the query, 0 (irrelevant) to 10 "
                "(directly answers it). Return one score per chunk_id, using the "
                "exact chunk_id shown in brackets."
            )},
            {"role": "user", "content": f"Query: {query}\n\nChunks:\n{candidates_block}"},
        ],
        response_format=BatchRerankResult,
    )

    scores_by_id = {s.chunk_id: s.relevance_score for s in response.choices[0].message.parsed.scores}
    for candidate in candidates:
        candidate["rerank_score"] = scores_by_id.get(candidate["chunk_id"], 0)

    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:keep_top_n]
