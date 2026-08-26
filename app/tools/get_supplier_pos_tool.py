"""List a supplier's purchase orders, optionally filtered by status."""

from pydantic import Field

from app.domain.enums import CanonicalEntityType, PurchaseOrderStatus
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.supplier_repository import SupplierRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema
from app.tools.resolve_entity_tool import resolve_trusted_search_term

_supplier_repo = SupplierRepository()
_purchase_order_repo = PurchaseOrderRepository()


def _format_po_with_provenance(po, state: SessionState) -> str:
    """Same fields as `PurchaseOrder.to_llm_readable_output()`, but with
    quantity/received_quantity tagged with ledger refs -- those are the
    two numbers a user could ask `final_answer` to repeat back to them.
    """
    quantity_tagged = state.provenance.tag("sql", f"{po.reference_code} quantity", po.quantity)
    received_tagged = state.provenance.tag("sql", f"{po.reference_code} received_quantity", po.received_quantity)
    due = po.due_date.isoformat() if po.due_date else "unspecified"
    return (
        f"PO {po.reference_code}: status={po.status.value}, "
        f"quantity={quantity_tagged}, received={received_tagged}, due={due}"
    )


class GetSupplierPOsTool(ToolSchema):
    TOOL_NAME = "get_supplier_pos"
    TOOL_DESCRIPTION = "List a supplier's purchase orders, optionally filtered by status."
    REQUIRES_PLAN = True
    SOURCE_KIND = "sql"

    supplier_search: str = Field(
        description="The supplier's reference code (e.g. 'SUP-1043') or name/partial name (e.g. 'Supplier B')."
    )
    status: PurchaseOrderStatus | None = Field(
        default=None, description="Optionally filter to only POs in this status."
    )

    def run(self, state: SessionState) -> str:
        # See get_customer_outstanding_tool.py's run() for why this rewrite exists.
        search_term = resolve_trusted_search_term(
            state.tenant_id, CanonicalEntityType.SUPPLIER, self.supplier_search
        )
        try:
            supplier = _supplier_repo.find_one_by_search_term(state.tenant_id, search_term)
        except ValueError:
            return f"Multiple suppliers match '{self.supplier_search}', be more specific."
        if supplier is None:
            return f"No supplier matching '{self.supplier_search}'."

        pos = _purchase_order_repo.list_by_supplier_reference_code(
            state.tenant_id, supplier.reference_code, self.status
        )
        if not pos:
            return f"No purchase orders found for supplier {supplier.reference_code}."
        return "\n".join(_format_po_with_provenance(po, state) for po in pos)
