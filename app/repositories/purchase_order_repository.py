"""Row<->entity mapping for `purchase_orders`."""

from app.db import run_query
from app.domain.entities import PurchaseOrder
from app.domain.enums import PurchaseOrderStatus


def _to_entity(row: dict) -> PurchaseOrder:
    return PurchaseOrder(
        id=row["id"],
        tenant_id=row["tenant_id"],
        reference_code=row["reference_code"],
        supplier_id=row["supplier_id"],
        status=PurchaseOrderStatus(row["status"]),
        quantity=row["quantity"],
        received_quantity=row["received_quantity"],
        due_date=row["due_date"],
        created_at=row["created_at"],
    )


class PurchaseOrderRepository:
    def get_by_reference_code(self, tenant_id: str, reference_code: str) -> PurchaseOrder | None:
        rows = run_query(
            "SELECT * FROM purchase_orders WHERE tenant_id = %s AND reference_code = %s",
            (tenant_id, reference_code),
        )
        return _to_entity(rows[0]) if rows else None

    def list_by_supplier_reference_code(
        self, tenant_id: str, supplier_reference_code: str, status: PurchaseOrderStatus | None = None
    ) -> list[PurchaseOrder]:
        """List a supplier's purchase orders, looked up by the supplier's
        human-facing reference_code -- the caller (a repository or tool)
        never needs to know or pass the supplier's internal UUID.
        """
        sql = (
            "SELECT po.* FROM purchase_orders po "
            "JOIN suppliers s ON s.id = po.supplier_id "
            "WHERE po.tenant_id = %s AND s.reference_code = %s"
        )
        params: list = [tenant_id, supplier_reference_code]
        if status is not None:
            sql += " AND po.status = %s"
            params.append(status.value)
        sql += " ORDER BY po.created_at"
        rows = run_query(sql, tuple(params))
        return [_to_entity(row) for row in rows]

    def sum_quantities_for_tenant(
        self, tenant_id: str, status: PurchaseOrderStatus | None = None
    ) -> dict:
        """Total quantity ordered/received across every supplier -- POs have
        no monetary column, so this is the "total PO ___" that's actually
        answerable from this schema (units, not currency).
        """
        sql = (
            "SELECT COALESCE(SUM(quantity), 0) AS quantity, "
            "COALESCE(SUM(received_quantity), 0) AS received_quantity "
            "FROM purchase_orders WHERE tenant_id = %s"
        )
        params: list = [tenant_id]
        if status is not None:
            sql += " AND status = %s"
            params.append(status.value)
        rows = run_query(sql, tuple(params))
        return {
            "quantity": rows[0]["quantity"],
            "received_quantity": rows[0]["received_quantity"],
        }
