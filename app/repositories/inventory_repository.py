"""Row<->entity mapping for `inventory`."""

from __future__ import annotations

from app.db import run_query
from app.domain.entities import InventoryItem


def _to_entity(row: dict) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        tenant_id=row["tenant_id"],
        sku=row["sku"],
        description=row["description"],
        quantity=row["quantity"],
    )


class InventoryRepository:
    def find_one_by_search_term(self, tenant_id: str, search_term: str) -> InventoryItem | None:
        rows = run_query(
            "SELECT * FROM inventory WHERE tenant_id = %s "
            "AND (sku = %s OR description ILIKE %s)",
            (tenant_id, search_term, f"%{search_term}%"),
        )
        if len(rows) > 1:
            raise ValueError(f"multiple inventory items match '{search_term}'")
        return _to_entity(rows[0]) if rows else None

    def list_all(self, tenant_id: str) -> list[InventoryItem]:
        rows = run_query(
            "SELECT * FROM inventory WHERE tenant_id = %s ORDER BY sku", (tenant_id,)
        )
        return [_to_entity(row) for row in rows]
