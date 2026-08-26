"""Precomputes embeddings for entity-linking text -- supplier/customer
names and knowledge_base's already-confirmed aliases -- so
`resolve_entity`'s semantic candidate scoring never has to call the
embeddings API for anything but the incoming mention itself.

Content-addressed, not row-ID-addressed: keyed by lowercased text, not
canonical_id. Supplier/customer UUIDs regenerate on every `run.sh` reseed,
but names and aliases are stable, so this cache never goes stale and only
ever pays for names/aliases it hasn't seen before -- unlike chat
embeddings, it needs no --reseed flag.

Run with: python db/embed_entities.py (after both seed_tenant_*.py have run).

Writes db/entity_embeddings.json: {"<lowercased text>": [vector]}.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.agent.openai_client import get_client
from app.db import close_pool, run_query

_OUTPUT_PATH = Path(__file__).resolve().parent / "entity_embeddings.json"


def _collect_texts() -> set[str]:
    texts: set[str] = set()
    for row in run_query("SELECT DISTINCT name FROM suppliers"):
        texts.add(row["name"])
    for row in run_query("SELECT DISTINCT name FROM customers"):
        texts.add(row["name"])
    for row in run_query(
        "SELECT DISTINCT alias_text FROM knowledge_base WHERE source IN ('reviewed', 'user_confirmed')"
    ):
        texts.add(row["alias_text"])
    return texts


def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = get_client()
    response = client.embeddings.create(model=config.OPENAI_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main() -> None:
    cache: dict[str, list[float]] = {}
    if _OUTPUT_PATH.exists():
        cache = json.loads(_OUTPUT_PATH.read_text())

    wanted = _collect_texts()
    missing = sorted(t for t in wanted if t.lower().strip() not in cache)

    if missing:
        vectors = _embed_batch(missing)
        for text, vector in zip(missing, vectors):
            cache[text.lower().strip()] = vector
        print(f"Embedded {len(missing)} new name(s)/alias(es).")
    else:
        print("No new names/aliases to embed -- cache already up to date.")

    _OUTPUT_PATH.write_text(json.dumps(cache))
    print(f"Wrote {_OUTPUT_PATH} ({len(cache)} entries total).")


if __name__ == "__main__":
    main()

    close_pool()
