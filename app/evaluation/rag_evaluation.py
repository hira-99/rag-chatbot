"""Runs the retrieval test cases (app/evaluation/datasets.py) against the
real retrieval service (Section D's hybrid_search) and scores them with
retrieval_metrics.py -- not a notebook demo corpus.
"""
from app.evaluation.datasets import RETRIEVAL_TEST_CASES
from app.evaluation.retrieval_metrics import hit_rate_at_k, mean_reciprocal_rank, precision_at_k, recall_at_k
from app.retrieval.hybrid_search import hybrid_search

K_VALUES = [1, 3, 5]


def run_retrieval_evaluation(test_cases=RETRIEVAL_TEST_CASES, k_values=K_VALUES):
    results = []
    for case in test_cases:
        candidates = hybrid_search(case.query, top_k=max(k_values))
        retrieved_ids = [c["chunk_id"] for c in candidates]

        case_result = {
            "case_id": case.case_id, "query": case.query, "category": case.category, "retrieved_ids": retrieved_ids,
        }
        for k in k_values:
            case_result[f"hit_rate@{k}"] = hit_rate_at_k(retrieved_ids, case.expected_chunk_ids, k)
            case_result[f"recall@{k}"] = recall_at_k(retrieved_ids, case.expected_chunk_ids, k)
            case_result[f"precision@{k}"] = precision_at_k(retrieved_ids, case.expected_chunk_ids, k)
        case_result["mrr"] = mean_reciprocal_rank(retrieved_ids, case.expected_chunk_ids)
        results.append(case_result)

    aggregate = {"avg_mrr": sum(r["mrr"] for r in results) / len(results)} if results else {"avg_mrr": 0.0}
    for k in k_values:
        aggregate[f"avg_hit_rate@{k}"] = sum(r[f"hit_rate@{k}"] for r in results) / len(results) if results else 0.0
        aggregate[f"avg_recall@{k}"] = sum(r[f"recall@{k}"] for r in results) / len(results) if results else 0.0
        aggregate[f"avg_precision@{k}"] = sum(r[f"precision@{k}"] for r in results) / len(results) if results else 0.0

    return {"cases": results, "aggregate": aggregate}
