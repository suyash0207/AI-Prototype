"""Row<->entity mapping for `orders`."""

from datetime import date

from app.db import run_query
from app.domain.entities import Order
from app.domain.enums import OrderStatus


def _to_entity(row: dict) -> Order:
    return Order(
        id=row["id"],
        tenant_id=row["tenant_id"],
        reference_code=row["reference_code"],
        customer_id=row["customer_id"],
        status=OrderStatus(row["status"]),
        promised_date=row["promised_date"],
        created_at=row["created_at"],
    )


class OrderRepository:
    def list_late(self, tenant_id: str, as_of_date: date) -> list[Order]:
        """Orders that are neither delivered nor cancelled and whose
        promised date has already passed as of `as_of_date`.
        """
        rows = run_query(
            "SELECT * FROM orders WHERE tenant_id = %s "
            "AND status NOT IN ('delivered', 'cancelled') "
            "AND promised_date < %s "
            "ORDER BY promised_date",
            (tenant_id, as_of_date),
        )
        return [_to_entity(row) for row in rows]
