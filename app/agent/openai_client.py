"""Thin wrapper around the OpenAI client so the rest of the codebase
never has to worry about how/when it gets constructed.
"""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app import config


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return OpenAI(api_key=config.OPENAI_API_KEY)
