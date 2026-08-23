"""Which tools belong to which agent -- kept separate from the tools
themselves so each tool file stays a single, self-contained unit that
doesn't need to know who uses it.
"""

from __future__ import annotations

from app.tools.confirm_entity_link_tool import ConfirmEntityLinkTool
from app.tools.get_customer_outstanding_tool import GetCustomerOutstandingTool
from app.tools.get_late_orders_tool import GetLateOrdersTool
from app.tools.get_supplier_pos_tool import GetSupplierPOsTool
from app.tools.get_total_outstanding_tool import GetTotalOutstandingTool
from app.tools.get_total_po_quantity_tool import GetTotalPOQuantityTool
from app.tools.list_customers_tool import ListCustomersTool
from app.tools.list_invoices_tool import ListInvoicesTool
from app.tools.list_suppliers_tool import ListSuppliersTool
from app.tools.resolve_entity_tool import ResolveEntityTool

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
