"""Duplicate/conflict detection before saving a new memory (Step 14.8-14.9):
compare against the user's existing memories and decide whether to skip,
supersede, or store as a new, separate memory.
"""
import json

from app.memory.retrieval import cosine_similarity


# Calibrated against real text-embedding-3-small scores (confirmed live),
# not guessed -- a same-fact paraphrase scored 0.82, a same-topic
# contradiction scored 0.72, an unrelated pair scored 0.18. The original
# guesses (0.92/0.80) would have let the paraphrase through as a second
# "store" and missed the contradiction as a conflict entirely.
DUPLICATE_THRESHOLD = 0.80  # near-identical or paraphrased -- don't store it again
CONFLICT_THRESHOLD = 0.65  # same topic, possibly contradicting -- supersede


def find_most_similar_memory(new_embedding, existing_memories):
    best, best_score = None, 0.0
    for memory in existing_memories:
        score = cosine_similarity(new_embedding, json.loads(memory["embedding"]))
        if score > best_score:
            best, best_score = memory, score
    return best, best_score


def decide_action(new_embedding, existing_memories):
    """Returns ("skip", memory) | ("supersede", memory) | ("store", None)."""
    best, score = find_most_similar_memory(new_embedding, existing_memories)
    if best is None:
        return "store", None
    if score >= DUPLICATE_THRESHOLD:
        return "skip", best
    if score >= CONFLICT_THRESHOLD:
        return "supersede", best
    return "store", None
