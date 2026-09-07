"""Chunking strategy.

Step 9's notebook compares five strategies (fixed-character, token-based,
paragraph-based, heading-aware, recursive). The app doesn't need to expose
that choice to users -- token-based chunking with overlap is the single
default: it bounds chunk size in the unit embeddings actually care about,
and overlap keeps a fact near a chunk boundary from being split away from
its context.
"""
import tiktoken

_encoding = tiktoken.get_encoding("cl100k_base")

CHUNK_SIZE_TOKENS = 300
CHUNK_OVERLAP_TOKENS = 50


def chunk_text(text, chunk_size=CHUNK_SIZE_TOKENS, overlap=CHUNK_OVERLAP_TOKENS):
    token_ids = _encoding.encode(text)
    if not token_ids:
        return []

    chunks = []
    start = 0
    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))
        chunks.append(_encoding.decode(token_ids[start:end]))
        if end == len(token_ids):
            break
        start += chunk_size - overlap
    return chunks
