"""Embedding generation wrapper."""
from app.config import EMBEDDING_MODEL
from app.llm.client import client


def get_embedding(text):
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding
