"""Total PO quantity ordered/received/pending across ALL suppliers.

Purchase orders have no monetary column in this schema -- this is the
"total PO ___" that's actually answerable (units, not currency).
"""

from pydantic import Field

from app.domain.enums import PurchaseOrderStatus
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_purchase_order_repo = PurchaseOrderRepository()


class GetTotalPOQuantityTool(ToolSchema):
    TOOL_NAME = "get_total_po_quantity"
    TOOL_DESCRIPTION = (
        "Total PO quantity ordered/received/pending across ALL suppliers, optionally filtered "
        "by status. Purchase orders have no monetary amount in this schema -- use this for "
        "'total units on order' questions, not ₹ value questions."
    )

    status: PurchaseOrderStatus | None = Field(
        default=None, description="Optionally filter to only POs in this status."
    )

    def run(self, state: SessionState) -> str:
        totals = _purchase_order_repo.sum_quantities_for_tenant(state.tenant_id, self.status)
        quantity = totals["quantity"]
        received = totals["received_quantity"]
        pending = quantity - received

        label = f"purchase orders across all suppliers (status={self.status.value})" if self.status else (
            "purchase orders across all suppliers (any status)"
        )
        quantity_tagged = state.provenance.tag("sql", f"total quantity for {label}", quantity)
        received_tagged = state.provenance.tag("sql", f"total received for {label}", received)
        pending_tagged = state.provenance.tag("sql", f"total pending for {label}", pending)
        scope = f"status={self.status.value}" if self.status else "any status"
        return (
            f"Tenant PO totals ({scope}): "
            f"quantity={quantity_tagged}, received={received_tagged}, pending={pending_tagged}. "
            f"Note: purchase orders track quantity/status only, not a monetary amount -- "
            f"there is no ₹ value to total here."
        )
