"""List every customer for this tenant -- backs broad "what's going on
here" questions where the model doesn't yet have a specific name to
search for.
"""

from app.repositories.customer_repository import CustomerRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_customer_repo = CustomerRepository()


class ListCustomersTool(ToolSchema):
    TOOL_NAME = "list_customers"
    TOOL_DESCRIPTION = (
        "List every customer for this tenant (name + reference code). Use this for broad "
        "'what's going on'/'give me an overview' questions where you don't yet have a "
        "specific customer name to search for."
    )

    def run(self, state: SessionState) -> str:
        customers = _customer_repo.list_all(state.tenant_id)
        if not customers:
            return "No customers found for this tenant."
        return "\n".join(c.to_llm_readable_output() for c in customers)
