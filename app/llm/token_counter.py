"""Token counting utilities."""
import tiktoken

_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(_encoding.encode(text or ""))
