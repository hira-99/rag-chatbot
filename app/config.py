"""Application configuration: env vars, model names, index names, limits."""
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4.1-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# Placeholder until real authentication exists (later reliability/security stage).
DEFAULT_USER_ID = "local-user"
