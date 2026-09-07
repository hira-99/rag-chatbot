"""Content hashing used to detect a byte-identical re-upload (C.5)."""
import hashlib


def content_hash(raw_bytes):
    return hashlib.sha256(raw_bytes).hexdigest()
