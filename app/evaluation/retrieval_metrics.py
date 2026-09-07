"""Retrieval metrics (Step 12.3): Hit rate@k, Recall@k, Precision@k,
Mean Reciprocal Rank. Each takes a ranked list of retrieved chunk_ids and
the set of expected ones.
"""


def hit_rate_at_k(retrieved_ids, expected_ids, k):
    top_k = retrieved_ids[:k]
    return 1.0 if any(cid in expected_ids for cid in top_k) else 0.0


def recall_at_k(retrieved_ids, expected_ids, k):
    if not expected_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & set(expected_ids)) / len(expected_ids)


def precision_at_k(retrieved_ids, expected_ids, k):
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for cid in top_k if cid in expected_ids)
    return hits / len(top_k)


def mean_reciprocal_rank(retrieved_ids, expected_ids):
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in expected_ids:
            return 1 / rank
    return 0.0
