"""Precomputes chat message embeddings so `search_messages` never has to
call the embeddings API at request time for anything but the query itself.

Run with: python chat_data/seed_messages.py (after generate_messages.py
has written the raw *_messages.json files).

Writes `chat_data/embeddings.json`: {tenant_id: [{message_id, vector}]}.
No pgvector, no external vector DB -- `app/tools/search_tools.py` loads
this file into memory once at process startup and does plain numpy
cosine similarity, which is more than fast enough at this data volume.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.agent.openai_client import get_client

_DATA_DIR = Path(__file__).resolve().parent
_TENANT_FILES = {
    "tenant_a": _DATA_DIR / "tenant_a_messages.json",
    "tenant_b": _DATA_DIR / "tenant_b_messages.json",
}


def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = get_client()
    response = client.embeddings.create(model=config.OPENAI_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main() -> None:
    result: dict[str, list[dict]] = {}
    for tenant_id, path in _TENANT_FILES.items():
        messages = json.loads(path.read_text())
        vectors = _embed_batch([m["text"] for m in messages])
        result[tenant_id] = [
            {"message_id": m["message_id"], "vector": vector}
            for m, vector in zip(messages, vectors)
        ]
        print(f"Embedded {len(messages)} messages for {tenant_id}.")

    (_DATA_DIR / "embeddings.json").write_text(json.dumps(result))
    print("Wrote chat_data/embeddings.json")


if __name__ == "__main__":
    main()
