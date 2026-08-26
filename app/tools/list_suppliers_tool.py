"""List every supplier for this tenant -- backs broad "what's going on
here" questions where the model doesn't yet have a specific name to
search for.
"""

from app.repositories.supplier_repository import SupplierRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_supplier_repo = SupplierRepository()


class ListSuppliersTool(ToolSchema):
    TOOL_NAME = "list_suppliers"
    TOOL_DESCRIPTION = (
        "List every supplier for this tenant (name + reference code). Use this for broad "
        "'what's going on'/'give me an overview' questions where you don't yet have a "
        "specific supplier name to search for."
    )
    REQUIRES_PLAN = True
    SOURCE_KIND = "sql"

    def run(self, state: SessionState) -> str:
        suppliers = _supplier_repo.list_all(state.tenant_id)
        if not suppliers:
            return "No suppliers found for this tenant."
        return "\n".join(s.to_llm_readable_output() for s in suppliers)
