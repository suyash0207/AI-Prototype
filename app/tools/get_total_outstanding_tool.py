"""Total invoiced/paid/outstanding across ALL customers for this tenant --
for "how much overall are we owed" questions, not just one customer.
"""

from app.repositories.invoice_repository import InvoiceRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_invoice_repo = InvoiceRepository()


class GetTotalOutstandingTool(ToolSchema):
    TOOL_NAME = "get_total_outstanding"
    TOOL_DESCRIPTION = (
        "Total invoiced/paid/outstanding across ALL customers for this tenant. Use this for "
        "'how much overall are we owed' questions, not just one customer."
    )
    REQUIRES_PLAN = True
    SOURCE_KIND = "sql"

    def run(self, state: SessionState) -> str:
        invoiced = _invoice_repo.sum_amount_for_tenant(state.tenant_id)
        paid = _invoice_repo.sum_paid_for_tenant(state.tenant_id)
        outstanding = invoiced - paid

        invoiced_tagged = state.provenance.tag("sql", "invoices for all customers", invoiced)
        paid_tagged = state.provenance.tag("sql", "payments for all customers", paid)
        outstanding_tagged = state.provenance.tag(
            "sql", "invoices minus payments for all customers", outstanding
        )
        return (
            f"Tenant totals across all customers: "
            f"invoiced={invoiced_tagged}, paid={paid_tagged}, outstanding={outstanding_tagged}"
        )
