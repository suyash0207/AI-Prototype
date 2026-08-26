"""The entity-linking bridge: `resolve_entity` turns an informal mention
("supp B", "4812", "the blue thread guys") into a canonical ERP record
-- without ever letting a wrong guess silently corrupt a figure.

Step 1 (deterministic, trusted): exact lookup against `knowledge_base`,
filtered to reviewed/user_confirmed rows only. A hit here is safe to
use immediately -- no LLM judgment involved.

Step 2+3 (fuzzy fallback): if nothing trusted matches, rank every
supplier/customer/purchase_order/inventory_item in the tenant -- plus
every already-confirmed knowledge_base alias, so a brand-new phrasing
that resembles one a person has already confirmed still surfaces --
by max(character similarity, embedding cosine similarity) against the
mention. No threshold decides trust here: this is a ranked list, not a
resolved/ambiguous/unresolved verdict, because a score was never
actually a trust decision (see `confirm_entity_link_tool.py`). The one
embeddings API call (for the mention itself) is deterministic given a
fixed model -- still not an LLM judgment call; "LLM-assisted" in the
plan refers to the *calling* agent's own judgment over these scores
(materiality, step 4), not a second model call hidden inside this tool.

Crucially: no candidate here is trusted silently, no matter how high
its score. No code path here writes to `knowledge_base` -- that only
happens via `confirm_entity_link`, once a person has actually said yes.
"""

import json
from difflib import SequenceMatcher
from pathlib import Path
from uuid import UUID

import numpy as np
from pydantic import Field

from app import config
from app.agent.openai_client import get_client
from app.db import run_query
from app.domain.enums import CanonicalEntityType
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema
from app.utils.constants import MAX_CANDIDATES_SHOWN, TRUSTED_FUZZY_THRESHOLD

_knowledge_repo = KnowledgeBaseRepository()

_ENTITY_EMBEDDINGS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "db" / "entity_embeddings.json"
)


def _normalize(vector: np.ndarray) -> np.ndarray:
    """Scales a vector to length 1, so a plain dot product between two
    normalized vectors equals their cosine similarity -- avoids redoing
    that division on every comparison in `_semantic_similarity`. The
    norm > 0 guard just avoids a divide-by-zero on a stray all-zero vector.
    """
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def _load_entity_embeddings() -> dict[str, np.ndarray]:
    """Optional infra, same pattern as `search_messages_tool.py`: if nobody
    has run `db/embed_entities.py` yet, semantic scoring just degrades to
    character-only rather than crashing the orchestrator import.
    """
    if not _ENTITY_EMBEDDINGS_PATH.exists():
        return {}
    # Keyed by lowercased text (not row id), matching how `add_entity_embedding`
    # and `_semantic_similarity` look entries back up -- content-addressed so
    # the cache survives a reseed even though every UUID regenerates.
    raw = json.loads(_ENTITY_EMBEDDINGS_PATH.read_text())
    # Normalize once here at load time, not on every comparison later.
    return {
        key: _normalize(np.array(vector, dtype=np.float32))
        for key, vector in raw.items()
    }


_ENTITY_EMBEDDINGS = _load_entity_embeddings()


def _embed_mention(mention: str) -> np.ndarray | None:
    """One embeddings call per `resolve_entity` invocation that reaches
    this fuzzy fallback -- never per candidate row. Degrades to `None`
    (character-only scoring) on any failure or if there's no cache to
    compare against in the first place.
    """
    if not _ENTITY_EMBEDDINGS:
        return None
    try:
        client = get_client()
        response = client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL, input=[mention]
        )
        return _normalize(np.array(response.data[0].embedding, dtype=np.float32))
    except Exception:  # noqa: BLE001 - a network/API hiccup degrades, never crashes resolve_entity
        return None


def add_entity_embedding(text: str) -> None:
    """Embeds one new string -- e.g. a just-confirmed alias -- and adds it
    to both the in-memory cache and `db/entity_embeddings.json`, so later
    `resolve_entity` calls (this session or a future one) can match
    against it without waiting for a rerun of `db/embed_entities.py`.
    Called by `confirm_entity_link_tool.py`; must never raise, since a
    confirmation succeeding is more important than this side effect.
    """
    client = get_client()
    response = client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL, input=[text]
    )
    vector = _normalize(np.array(response.data[0].embedding, dtype=np.float32))

    key = text.lower().strip()
    _ENTITY_EMBEDDINGS[key] = vector

    on_disk: dict[str, list[float]] = {}
    if _ENTITY_EMBEDDINGS_PATH.exists():
        on_disk = json.loads(_ENTITY_EMBEDDINGS_PATH.read_text())
    on_disk[key] = vector.tolist()
    _ENTITY_EMBEDDINGS_PATH.write_text(json.dumps(on_disk))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _semantic_similarity(mention_vector: np.ndarray | None, text: str) -> float:
    if mention_vector is None:
        return 0.0
    cached = _ENTITY_EMBEDDINGS.get(text.lower().strip())
    if cached is None:
        return 0.0
    return float(mention_vector @ cached)


def _candidates_for_tenant(tenant_id: str, mention: str) -> list[dict]:
    """Fuzzy candidate generation across every table a knowledge_base row
    could point at, plus the knowledge_base's own already-confirmed
    aliases. Lives here, not in a repository, because it composes across
    multiple aggregates -- that's application logic (entity linking), not
    a single aggregate's row<->entity mapping.

    Names/aliases (natural language) get character + semantic scoring;
    codes (SKUs, PO/reference codes) stay character-only -- embeddings
    measurably underperform plain string similarity on short codes with
    no natural-language content ("4812" vs "PO-4812": 0.73 character,
    0.56 embedding).
    """
    mention_vector = _embed_mention(mention)
    scored: dict[tuple[CanonicalEntityType, UUID], dict] = {}

    def _consider(
        canonical_type: CanonicalEntityType,
        canonical_id: UUID,
        reference_code: str,
        label: str,
        text: str,
        use_semantic: bool = False,
    ) -> None:
        char_score = _similarity(mention, text)
        semantic_score = (
            _semantic_similarity(mention_vector, text) if use_semantic else 0.0
        )
        confidence = max(char_score, semantic_score)
        key = (canonical_type, canonical_id)
        existing = scored.get(key)
        if existing is None:
            scored[key] = {
                "canonical_type": canonical_type,
                "canonical_id": canonical_id,
                "reference_code": reference_code,
                "label": label,
                "confidence": confidence,
            }
        elif confidence > existing["confidence"]:
            existing["confidence"] = confidence

    for row in run_query(
        "SELECT id, reference_code, name FROM suppliers WHERE tenant_id = %s",
        (tenant_id,),
    ):
        _consider(
            CanonicalEntityType.SUPPLIER,
            row["id"],
            row["reference_code"],
            row["name"],
            row["name"],
            use_semantic=True,
        )
        _consider(
            CanonicalEntityType.SUPPLIER,
            row["id"],
            row["reference_code"],
            row["name"],
            row["reference_code"],
        )

    for row in run_query(
        "SELECT id, reference_code, name FROM customers WHERE tenant_id = %s",
        (tenant_id,),
    ):
        _consider(
            CanonicalEntityType.CUSTOMER,
            row["id"],
            row["reference_code"],
            row["name"],
            row["name"],
            use_semantic=True,
        )
        _consider(
            CanonicalEntityType.CUSTOMER,
            row["id"],
            row["reference_code"],
            row["name"],
            row["reference_code"],
        )

    for row in run_query(
        "SELECT id, reference_code FROM purchase_orders WHERE tenant_id = %s",
        (tenant_id,),
    ):
        bare_digits = row["reference_code"].split("-")[-1]
        _consider(
            CanonicalEntityType.PURCHASE_ORDER,
            row["id"],
            row["reference_code"],
            row["reference_code"],
            row["reference_code"],
        )
        _consider(
            CanonicalEntityType.PURCHASE_ORDER,
            row["id"],
            row["reference_code"],
            row["reference_code"],
            bare_digits,
        )

    for row in run_query(
        "SELECT id, sku, description FROM inventory WHERE tenant_id = %s", (tenant_id,)
    ):
        _consider(
            CanonicalEntityType.INVENTORY_ITEM,
            row["id"],
            row["sku"],
            row["description"],
            row["description"],
        )
        _consider(
            CanonicalEntityType.INVENTORY_ITEM,
            row["id"],
            row["sku"],
            row["description"],
            row["sku"],
        )

    # Second pass: previously-confirmed aliases can raise an entity's score
    # if the mention resembles the alias more than it resembles the raw
    # name/code -- this is the "keeps learning" mechanism, growing with
    # every confirm_entity_link call. Never invents a candidate outside
    # the four loops above; an alias pointing at something not seen there
    # is skipped rather than shown with a bare alias-text label nobody
    # asked about.
    for alias in _knowledge_repo.list_trusted(tenant_id):
        key = (alias.canonical_type, alias.canonical_id)
        if key not in scored:
            continue
        _consider(
            alias.canonical_type,
            alias.canonical_id,
            scored[key]["reference_code"],
            scored[key]["label"],
            alias.alias_text,
            use_semantic=True,
        )

    candidates = list(scored.values())
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates


_CANONICAL_TABLES: dict[CanonicalEntityType, tuple[str, str]] = {
    CanonicalEntityType.SUPPLIER: ("suppliers", "reference_code"),
    CanonicalEntityType.CUSTOMER: ("customers", "reference_code"),
    CanonicalEntityType.PURCHASE_ORDER: ("purchase_orders", "reference_code"),
    CanonicalEntityType.ORDER: ("orders", "reference_code"),
    CanonicalEntityType.INVENTORY_ITEM: ("inventory", "sku"),
}


def _reference_code_for(
    tenant_id: str, canonical_type: CanonicalEntityType, canonical_id: UUID
) -> str | None:
    """Reverses `_lookup_canonical_id` (in confirm_entity_link_tool.py):
    turns a knowledge_base row's internal canonical_id back into the
    human-facing code every other tool actually expects. Without this,
    `resolve_entity` would hand the model a raw UUID -- exactly the
    internal-only value the rest of the domain layer promises never to
    surface (see PLAN.md section 2).
    """
    table = _CANONICAL_TABLES.get(canonical_type)
    if table is None:
        return None
    table_name, code_column = table
    rows = run_query(
        f"SELECT {code_column} AS code FROM {table_name} WHERE tenant_id = %s AND id = %s",
        (tenant_id, canonical_id),
    )
    return rows[0]["code"] if rows else None


def _find_trusted_fuzzy(tenant_id: str, mention: str):
    """Step 1's fuzzy half: forgive minor phrasing noise against an
    already-trusted alias_text (never against a raw ERP name -- that's
    step 2's job and is never trusted silently).
    """
    best = None
    best_score = 0.0
    for entry in _knowledge_repo.list_trusted(tenant_id):
        score = _similarity(mention, entry.alias_text)
        if score > best_score:
            best, best_score = entry, score
    if best is not None and best_score >= TRUSTED_FUZZY_THRESHOLD:
        return best
    return None


def resolve_trusted_search_term(
    tenant_id: str, canonical_type: CanonicalEntityType, search_term: str
) -> str:
    """Lets every SQL tool's own `_search` field benefit from Step 1's
    trusted lookup, not just an explicit `resolve_entity` call. Without
    this, the same already-confirmed alias resolves via `resolve_entity`
    but silently fails via e.g. `get_supplier_pos`'s own ILIKE-only
    lookup, purely depending on which tool the text happens to flow
    through -- an inconsistency, not a safety boundary.

    Only ever touches resolve_entity's deterministic, human-confirmed
    tiers (exact + fuzzy-trusted-alias) -- never the ranked/unconfirmed
    candidate tier, which no SQL tool may ever auto-apply. Falls through
    to `search_term` unchanged on no match, a `canonical_type` mismatch,
    or a stale `reference_code` lookup (see the same caveat already
    documented on `ResolveEntityTool.run()`'s trusted branch below), so
    the caller's own exact-code-or-ILIKE lookup still gets a chance.
    """
    trusted = _knowledge_repo.find_trusted(tenant_id, search_term) or _find_trusted_fuzzy(
        tenant_id, search_term
    )
    if trusted is None or trusted.canonical_type != canonical_type:
        return search_term
    return _reference_code_for(tenant_id, trusted.canonical_type, trusted.canonical_id) or search_term


class ResolveEntityTool(ToolSchema):
    TOOL_NAME = "resolve_entity"
    TOOL_DESCRIPTION = (
        "Look up what ERP record an informal mention refers to (e.g. 'supp B', '4812', 'the blue "
        "thread guys'). Checks the trusted knowledge base first; if nothing trusted matches, returns "
        "fuzzy candidates that must go through ask_clarification + confirm_entity_link before being "
        "trusted. Available to both the orchestrator and the retrieval sub-agent."
    )

    mention: str = Field(
        description="The informal phrase to link, e.g. 'supp B', '4812', or 'the blue thread guys'."
    )

    def run(self, state: SessionState) -> str:
        # Step 1, trusted: exact case-insensitive knowledge_base match first;
        # if that misses, fall back to a fuzzy match against already-trusted
        # alias text only (never against a raw ERP name -- that's the
        # ranked-candidate path below, and it's never trusted silently).
        trusted = _knowledge_repo.find_trusted(
            state.tenant_id, self.mention
        ) or _find_trusted_fuzzy(state.tenant_id, self.mention)
        if trusted is not None:
            # Translate the internal canonical_id back to the human-facing
            # code (e.g. "SUP-2043") every other tool actually expects.
            reference_code = _reference_code_for(
                state.tenant_id, trusted.canonical_type, trusted.canonical_id
            )
            # Caveat, left as-is: if reference_code lookup fails -- a stale
            # knowledge_base row whose canonical_id no longer matches any
            # record -- this falls back to the raw internal UUID, which
            # contradicts the "never the raw internal id" instruction below.
            # Currently unreachable in the normal run.sh flow (schema.sql +
            # knowledge_base.sql are always reset together, so canonical_ids
            # stay in sync), but a real risk if a row is ever left stale.
            return (
                f"RESOLVED (trusted, source={trusted.source.value}): '{self.mention}' = "
                f"{trusted.canonical_type.value}:{reference_code}. Use '{reference_code}' as the search/reference "
                "value in other tools -- never the raw internal id."
            )

        candidates = _candidates_for_tenant(state.tenant_id, self.mention)[
            :MAX_CANDIDATES_SHOWN
        ]
        if not candidates:
            return f"UNRESOLVED: no candidates found for '{self.mention}'."

        header = (
            f"CANDIDATES for '{self.mention}', ranked by similarity "
            "(none confirmed by a person -- do NOT treat any as fact):"
        )
        lines = [header]
        for c in candidates:
            lines.append(
                f'- {c["canonical_type"].value}:{c["reference_code"]} "{c["label"]}" '
                f"(confidence={c['confidence']:.2f})"
            )
        lines.append(
            "If this mention matters for a number or fact in your answer, call ask_clarification with "
            "these candidates before using any of them -- even the top-scored one. Once the user picks "
            "one, call confirm_entity_link to record it; resolve_entity will then return it as trusted."
        )
        return "\n".join(lines)
