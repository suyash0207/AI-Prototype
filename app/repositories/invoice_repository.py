"""Row<->entity mapping for `invoices`, plus the invoiced/paid/outstanding
sums that back `get_customer_outstanding`.
"""

from __future__ import annotations

from app.db import run_query
from app.domain.entities import Invoice


def _to_entity(row: dict) -> Invoice:
    return Invoice(
        id=row["id"],
        tenant_id=row["tenant_id"],
        reference_code=row["reference_code"],
        customer_id=row["customer_id"],
        amount=float(row["amount"]),
        created_at=row["created_at"],
    )


class InvoiceRepository:
    def list_by_customer_id(self, tenant_id: str, customer_id) -> list[Invoice]:
        rows = run_query(
            "SELECT * FROM invoices WHERE tenant_id = %s AND customer_id = %s ORDER BY created_at",
            (tenant_id, customer_id),
        )
        return [_to_entity(row) for row in rows]

    def sum_amount_for_customer(self, tenant_id: str, customer_id) -> float:
        """Total amount billed to this customer across every invoice."""
        rows = run_query(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM invoices "
            "WHERE tenant_id = %s AND customer_id = %s",
            (tenant_id, customer_id),
        )
        return float(rows[0]["total"])

    def sum_paid_for_customer(self, tenant_id: str, customer_id) -> float:
        """Total amount actually paid against this customer's invoices,
        via a join through `payments` -- payments don't carry customer_id
        directly, only invoice_id.
        """
        rows = run_query(
            "SELECT COALESCE(SUM(p.amount), 0) AS total FROM payments p "
            "JOIN invoices i ON i.id = p.invoice_id "
            "WHERE i.tenant_id = %s AND i.customer_id = %s",
            (tenant_id, customer_id),
        )
        return float(rows[0]["total"])

    def sum_amount_for_tenant(self, tenant_id: str) -> float:
        """Total amount billed across every customer -- backs tenant-wide
        "how much are we owed overall" questions, not just one customer.
        """
        rows = run_query(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM invoices WHERE tenant_id = %s",
            (tenant_id,),
        )
        return float(rows[0]["total"])

    def sum_paid_for_tenant(self, tenant_id: str) -> float:
        """Total amount actually paid across every customer's invoices."""
        rows = run_query(
            "SELECT COALESCE(SUM(p.amount), 0) AS total FROM payments p "
            "JOIN invoices i ON i.id = p.invoice_id "
            "WHERE i.tenant_id = %s",
            (tenant_id,),
        )
        return float(rows[0]["total"])
