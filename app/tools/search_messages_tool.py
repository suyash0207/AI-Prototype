"""In-memory semantic search over precomputed chat embeddings.

Loads `chat_data/embeddings.json` + the raw message JSON into memory
once, at import time (module-level, per-tenant numpy arrays) -- no
pgvector, no external vector DB, because the data volume here is small
enough that a plain in-process cosine-similarity scan is more than
fast enough and needs zero extra infrastructure.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pydantic import Field

from app import config
from app.agent.openai_client import get_client
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "chat_data"


class _TenantIndex:
    """One tenant's messages + their embedding matrix, held in memory."""

    def __init__(self, messages: list[dict], vectors: np.ndarray) -> None:
        self.messages = messages  # list[dict], same order as `vectors`' rows
        self.vectors = vectors  # shape (n_messages, embedding_dim), L2-normalized


def _load_indices() -> dict[str, _TenantIndex]:
    embeddings_path = _DATA_DIR / "embeddings.json"
    if not embeddings_path.exists():
        # Chat search is optional infra -- if nobody has run seed_messages.py
        # yet, search_messages degrades to "no results" rather than crashing
        # the whole orchestrator import.
        return {}

    raw_embeddings = json.loads(embeddings_path.read_text())
    indices: dict[str, _TenantIndex] = {}
    for tenant_id, entries in raw_embeddings.items():
        messages_path = _DATA_DIR / f"{tenant_id}_messages.json"
        messages_by_id = {m["message_id"]: m for m in json.loads(messages_path.read_text())}

        ordered_messages = [messages_by_id[e["message_id"]] for e in entries]
        matrix = np.array([e["vector"] for e in entries], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        indices[tenant_id] = _TenantIndex(ordered_messages, matrix)
    return indices


_INDICES = _load_indices()


def search_messages_for_tenant(tenant_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Embed `query` and return the top-k most similar messages for this
    tenant, each as {message_id, sender, timestamp, text, score}.

    Exposed as a plain function (not just the tool below) so this
    tool's `run()` and any future non-tool caller share one
    implementation.
    """
    index = _INDICES.get(tenant_id)
    if index is None or len(index.messages) == 0:
        return []

    client = get_client()
    response = client.embeddings.create(model=config.OPENAI_EMBEDDING_MODEL, input=[query])
    query_vector = np.array(response.data[0].embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_vector)
    if query_norm > 0:
        query_vector = query_vector / query_norm

    scores = index.vectors @ query_vector
    top_indices = np.argsort(-scores)[:top_k]

    return [
        {
            "message_id": index.messages[i]["message_id"],
            "sender": index.messages[i]["sender"],
            "timestamp": index.messages[i]["timestamp"],
            "text": index.messages[i]["text"],
            "score": float(scores[i]),
        }
        for i in top_indices
    ]


class SearchMessagesTool(ToolSchema):
    TOOL_NAME = "search_messages"
    TOOL_DESCRIPTION = "Semantic search over this tenant's chat history. Returns the top-k most relevant messages."

    query: str = Field(description="What to search for, in plain English.")
    top_k: int = Field(default=5, description="How many results to return, most relevant first.")

    def run(self, state: SessionState) -> str:
        results = search_messages_for_tenant(state.tenant_id, self.query, self.top_k)
        if not results:
            return f"No chat messages found for '{self.query}'."
        return "\n".join(
            f"[{r['message_id']}] {r['sender']} ({r['timestamp']}): {r['text']} (score={r['score']:.3f})"
            for r in results
        )
