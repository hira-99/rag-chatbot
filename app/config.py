"""Application configuration: env vars, model names, index names, limits."""
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4.1-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# Placeholder until real authentication exists (later reliability/security stage).
DEFAULT_USER_ID = "local-user"

# Retrieval stores (Section D). Chroma runs as a standalone container --
# it isn't in docker-compose.yml yet (see CLAUDE.md's known-gaps note).
ELASTICSEARCH_URL = "http://localhost:9200"
LEXICAL_INDEX_NAME = "rag_documents_app"
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
VECTOR_COLLECTION_NAME = "bytemage_app_docs"
