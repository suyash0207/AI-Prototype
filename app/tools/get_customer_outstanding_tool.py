"""Look up how much a customer currently owes (invoiced minus paid).

`tenant_id` is never a model-supplied argument -- `run()` reads
`state.tenant_id` so a cross-tenant leak is impossible by construction,
not because the model was trusted to pass the right id.
"""

from pydantic import Field

from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_customer_repo = CustomerRepository()
_invoice_repo = InvoiceRepository()


class GetCustomerOutstandingTool(ToolSchema):
    TOOL_NAME = "get_customer_outstanding"
    TOOL_DESCRIPTION = (
        "Look up how much a customer currently owes (invoiced minus paid), searched by "
        "reference code or name."
    )

    customer_search: str = Field(
        description="The customer's reference code (e.g. 'CUST-0078') or name/partial name (e.g. 'Sharma')."
    )

    def run(self, state: SessionState) -> str:
        try:
            customer = _customer_repo.find_one_by_search_term(state.tenant_id, self.customer_search)
        except ValueError:
            return f"Multiple customers match '{self.customer_search}', be more specific."
        if customer is None:
            return f"No customer matching '{self.customer_search}'."

        invoiced = _invoice_repo.sum_amount_for_customer(state.tenant_id, customer.id)
        paid = _invoice_repo.sum_paid_for_customer(state.tenant_id, customer.id)
        outstanding = invoiced - paid

        # Every number handed back to the model gets a ledger ref -- final_answer
        # can only cite figures that trace back to one of these, never invent one.
        invoiced_tagged = state.provenance.tag("sql", f"invoices for {customer.reference_code}", invoiced)
        paid_tagged = state.provenance.tag("sql", f"payments for {customer.reference_code}", paid)
        outstanding_tagged = state.provenance.tag(
            "sql", f"invoices minus payments for {customer.reference_code}", outstanding
        )
        return (
            f"{customer.name} ({customer.reference_code}): "
            f"invoiced={invoiced_tagged}, paid={paid_tagged}, outstanding={outstanding_tagged}"
        )
