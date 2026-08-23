"""Row<->entity mapping for `suppliers` -- the only place that knows both
the SQL column names and the `Supplier` entity shape.
"""

from __future__ import annotations

from app.db import run_query
from app.domain.entities import Supplier


def _to_entity(row: dict) -> Supplier:
    return Supplier(
        id=row["id"],
        tenant_id=row["tenant_id"],
        reference_code=row["reference_code"],
        name=row["name"],
    )


class SupplierRepository:
    def find_one_by_search_term(self, tenant_id: str, search_term: str) -> Supplier | None:
        """Look up a supplier by exact reference_code or partial name match.

        Exists because a user asks "what's up with Supplier B" using the
        ERP's own name, not its formal code -- the model has no way to
        already know "SUP-1043", so the lookup itself has to search on
        what a person would actually type. Returns None for zero matches;
        raises if more than one row matches so the caller can surface an
        unambiguous error rather than silently picking the first row.
        """
        rows = run_query(
            "SELECT * FROM suppliers WHERE tenant_id = %s "
            "AND (reference_code = %s OR name ILIKE %s)",
            (tenant_id, search_term, f"%{search_term}%"),
        )
        if len(rows) > 1:
            raise ValueError(f"multiple suppliers match '{search_term}'")
        return _to_entity(rows[0]) if rows else None

    def list_all(self, tenant_id: str) -> list[Supplier]:
        """All suppliers for a tenant -- backs broad "what's going on here"
        questions where the model doesn't yet have a specific name to search for.
        """
        rows = run_query(
            "SELECT * FROM suppliers WHERE tenant_id = %s ORDER BY reference_code",
            (tenant_id,),
        )
        return [_to_entity(row) for row in rows]
