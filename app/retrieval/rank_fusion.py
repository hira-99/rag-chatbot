"""Reciprocal Rank Fusion and related fusion utilities."""


def reciprocal_rank_fusion(ranked_lists, k=60):
    """Fuse any number of ranked result lists (each a list of dicts with at
    least 'chunk_id'/'text'/'metadata') into one, by RRF -- the same
    score = 1/(k+rank) summed across retrievers used in the notebooks."""
    fused = {}
    for results in ranked_lists.values():
        for rank, result in enumerate(results, start=1):
            chunk_id = result["chunk_id"]
            if chunk_id not in fused:
                fused[chunk_id] = {
                    "chunk_id": chunk_id,
                    "text": result["text"],
                    "metadata": result.get("metadata", {}),
                    "rrf_score": 0.0,
                }
            fused[chunk_id]["rrf_score"] += 1 / (k + rank)

    fused_list = list(fused.values())
    fused_list.sort(key=lambda entry: entry["rrf_score"], reverse=True)
    return fused_list
