"""List every individual invoice for a customer -- the actual line items,
not just the netted `get_customer_outstanding` total.
"""

from pydantic import Field

from app.domain.enums import CanonicalEntityType
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema
from app.tools.resolve_entity_tool import resolve_trusted_search_term

_customer_repo = CustomerRepository()
_invoice_repo = InvoiceRepository()


def _format_invoice_with_provenance(invoice, state: SessionState) -> str:
    """Same field as `Invoice.to_llm_readable_output()`, but with `amount`
    tagged with a ledger ref -- this is what makes individual invoice
    figures (not just the netted `get_customer_outstanding` total) citable.
    """
    amount_tagged = state.provenance.tag("sql", f"{invoice.reference_code} amount", invoice.amount)
    return f"Invoice {invoice.reference_code}: amount={amount_tagged}"


class ListInvoicesTool(ToolSchema):
    TOOL_NAME = "list_invoices"
    TOOL_DESCRIPTION = (
        "List every individual invoice for a customer (reference code + amount), searched by "
        "reference code or name. Use this when someone wants to see the actual invoice line "
        "items, not just the netted outstanding total."
    )
    REQUIRES_PLAN = True
    SOURCE_KIND = "sql"

    customer_search: str = Field(
        description="The customer's reference code (e.g. 'CUST-0078') or name/partial name (e.g. 'Sharma')."
    )

    def run(self, state: SessionState) -> str:
        # See get_customer_outstanding_tool.py's run() for why this rewrite exists.
        search_term = resolve_trusted_search_term(
            state.tenant_id, CanonicalEntityType.CUSTOMER, self.customer_search
        )
        try:
            customer = _customer_repo.find_one_by_search_term(state.tenant_id, search_term)
        except ValueError:
            return f"Multiple customers match '{self.customer_search}', be more specific."
        if customer is None:
            return f"No customer matching '{self.customer_search}'."

        invoices = _invoice_repo.list_by_customer_id(state.tenant_id, customer.id)
        if not invoices:
            return f"No invoices found for {customer.name} ({customer.reference_code})."
        return "\n".join(_format_invoice_with_provenance(inv, state) for inv in invoices)
