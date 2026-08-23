"""Environment configuration.

Imported first (before anything reads an env var) so that `.env`
is loaded exactly once for the whole process.
"""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
FSM_MAX_LLM_CALLS = int(os.getenv("FSM_MAX_LLM_CALLS", "10"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql:///two_worlds")
