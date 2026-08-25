"""The top-level agent: owns its tool registry and prompt, and drives
the shared workflow loop against whichever session it's handed.
"""

from pathlib import Path

from app.agent import fsm
from app.state.store import get_or_create_session
from app.tools.ask_clarification_tool import AskClarificationTool
from app.tools.base import build_tool_registry
from app.tools.confirm_entity_link_tool import ConfirmEntityLinkTool
from app.tools.final_answer_tool import FinalAnswerTool
from app.tools.get_customer_outstanding_tool import GetCustomerOutstandingTool
from app.tools.get_late_orders_tool import GetLateOrdersTool
from app.tools.get_supplier_pos_tool import GetSupplierPOsTool
from app.tools.get_total_outstanding_tool import GetTotalOutstandingTool
from app.tools.get_total_po_quantity_tool import GetTotalPOQuantityTool
from app.tools.list_customers_tool import ListCustomersTool
from app.tools.list_invoices_tool import ListInvoicesTool
from app.tools.list_suppliers_tool import ListSuppliersTool
from app.tools.resolve_entity_tool import ResolveEntityTool
from app.tools.retrieve_from_chat_tool import RetrieveFromChatTool

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()

SQL_TOOLS = [
    GetCustomerOutstandingTool,
    GetSupplierPOsTool,
    GetLateOrdersTool,
    ListCustomersTool,
    ListSuppliersTool,
    ListInvoicesTool,
    GetTotalOutstandingTool,
    GetTotalPOQuantityTool,
]

ENTITY_LINK_TOOLS = [ResolveEntityTool, ConfirmEntityLinkTool]

# `search_messages` is deliberately NOT here -- only the retrieval sub-agent
# (app/agent/retrieval_agent.py) calls it directly. The orchestrator only
# ever sees chat data as `retrieve_from_chat`'s structured, ledger-backed
# claims, never raw message text it could misquote.
ORCHESTRATOR_TOOLS = build_tool_registry(
    [FinalAnswerTool, AskClarificationTool, *SQL_TOOLS, RetrieveFromChatTool, *ENTITY_LINK_TOOLS]
)

# Currently I am only handling messages for a single tenant.
def handle_message(session_id: str, tenant_id: str, message: str) -> str:
    state = get_or_create_session(session_id, tenant_id, _SYSTEM_PROMPT)
    state.add_human_message(message)
    return fsm.run_workflow(state, ORCHESTRATOR_TOOLS)
