"""Row<->entity mapping for `knowledge_base` -- the trusted, curated
bridge between informal chat mentions and canonical ERP records.
"""

from __future__ import annotations

from uuid import UUID

from app.db import run_query
from app.domain.entities import KnowledgeBaseEntry
from app.domain.enums import CanonicalEntityType, KnowledgeSource


def _to_entity(row: dict) -> KnowledgeBaseEntry:
    return KnowledgeBaseEntry(
        id=row["id"],
        tenant_id=row["tenant_id"],
        alias_text=row["alias_text"],
        canonical_type=CanonicalEntityType(row["canonical_type"]),
        canonical_id=row["canonical_id"],
        confidence=float(row["confidence"]),
        source=KnowledgeSource(row["source"]),
    )


class KnowledgeBaseRepository:
    def find_trusted(self, tenant_id: str, alias_text: str) -> KnowledgeBaseEntry | None:
        """Exact, case-insensitive lookup against knowledge_base, filtered
        to source IN (reviewed, user_confirmed) -- only these are ever
        trusted silently. An llm_suggested row is a pending proposal
        nobody has looked at yet, and this method never returns one --
        that's the whole point of `resolve_entity`'s step 1.
        """
        rows = run_query(
            "SELECT * FROM knowledge_base WHERE tenant_id = %s AND lower(alias_text) = lower(%s) "
            "AND source IN ('reviewed', 'user_confirmed') "
            "ORDER BY (source = 'user_confirmed') DESC LIMIT 1",
            (tenant_id, alias_text),
        )
        return _to_entity(rows[0]) if rows else None

    def list_trusted(self, tenant_id: str) -> list[KnowledgeBaseEntry]:
        """Every reviewed/user_confirmed row for this tenant -- used to
        fuzzy-match minor phrasing variants ("the dye guys" vs "dye guys")
        against an *already-trusted* alias, as opposed to guessing against
        raw ERP names. See `resolve_entity`'s step 1 for why this still
        counts as deterministic/trusted rather than a fresh guess.
        """
        rows = run_query(
            "SELECT * FROM knowledge_base WHERE tenant_id = %s AND source IN ('reviewed', 'user_confirmed')",
            (tenant_id,),
        )
        return [_to_entity(row) for row in rows]

    def insert_user_confirmed(
        self, tenant_id: str, alias_text: str, canonical_type: CanonicalEntityType, canonical_id: UUID
    ) -> KnowledgeBaseEntry:
        """The promotion step: writes back what the user just confirmed in
        reply to an `ask_clarification` question, so next time this exact
        phrase appears (same tenant) `find_trusted` resolves it directly --
        no LLM call, no repeat question.
        """
        rows = run_query(
            "INSERT INTO knowledge_base (tenant_id, alias_text, canonical_type, canonical_id, confidence, source) "
            "VALUES (%s, %s, %s, %s, %s, 'user_confirmed') RETURNING *",
            (tenant_id, alias_text, canonical_type.value, canonical_id, 1.0),
        )
        return _to_entity(rows[0])
