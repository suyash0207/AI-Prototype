"""Direct, parametrized SQL tools -- deterministic, single-shot, no
reasoning loop. `tenant_id` is never a model-supplied argument; every
handler reads `state.tenant_id` so a cross-tenant leak is impossible
by construction, not because the model was trusted to pass the right id.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.enums import PurchaseOrderStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.supplier_repository import SupplierRepository
from app.state.session_state import SessionState
from app.tools.base import Tool

_customer_repo = CustomerRepository()
_supplier_repo = SupplierRepository()
_invoice_repo = InvoiceRepository()
_purchase_order_repo = PurchaseOrderRepository()
_order_repo = OrderRepository()


class GetCustomerOutstandingArgs(BaseModel):
    customer_search: str = Field(
        description="The customer's reference code (e.g. 'CUST-0078') or name/partial name (e.g. 'Sharma')."
    )


def _get_customer_outstanding(args: GetCustomerOutstandingArgs, state: SessionState) -> str:
    try:
        customer = _customer_repo.find_one_by_search_term(state.tenant_id, args.customer_search)
    except ValueError:
        return f"Multiple customers match '{args.customer_search}', be more specific."
    if customer is None:
        return f"No customer matching '{args.customer_search}'."

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


get_customer_outstanding_tool = Tool(
    name="get_customer_outstanding",
    description=(
        "Look up how much a customer currently owes (invoiced minus paid), searched by "
        "reference code or name."
    ),
    args_schema=GetCustomerOutstandingArgs,
    handler=_get_customer_outstanding,
)


class ListInvoicesArgs(BaseModel):
    customer_search: str = Field(
        description="The customer's reference code (e.g. 'CUST-0078') or name/partial name (e.g. 'Sharma')."
    )


def _list_invoices(args: ListInvoicesArgs, state: SessionState) -> str:
    try:
        customer = _customer_repo.find_one_by_search_term(state.tenant_id, args.customer_search)
    except ValueError:
        return f"Multiple customers match '{args.customer_search}', be more specific."
    if customer is None:
        return f"No customer matching '{args.customer_search}'."

    invoices = _invoice_repo.list_by_customer_id(state.tenant_id, customer.id)
    if not invoices:
        return f"No invoices found for {customer.name} ({customer.reference_code})."
    return "\n".join(_format_invoice_with_provenance(inv, state) for inv in invoices)


def _format_invoice_with_provenance(invoice, state: SessionState) -> str:
    """Same field as `Invoice.to_llm_readable_output()`, but with `amount`
    tagged with a ledger ref -- this is what makes individual invoice
    figures (not just the netted `get_customer_outstanding` total) citable.
    """
    amount_tagged = state.provenance.tag("sql", f"{invoice.reference_code} amount", invoice.amount)
    return f"Invoice {invoice.reference_code}: amount={amount_tagged}"


list_invoices_tool = Tool(
    name="list_invoices",
    description=(
        "List every individual invoice for a customer (reference code + amount), searched by "
        "reference code or name. Use this when someone wants to see the actual invoice line "
        "items, not just the netted outstanding total."
    ),
    args_schema=ListInvoicesArgs,
    handler=_list_invoices,
)


class ListCustomersArgs(BaseModel):
    pass


def _list_customers(args: ListCustomersArgs, state: SessionState) -> str:
    customers = _customer_repo.list_all(state.tenant_id)
    if not customers:
        return "No customers found for this tenant."
    return "\n".join(c.to_llm_readable_output() for c in customers)


list_customers_tool = Tool(
    name="list_customers",
    description=(
        "List every customer for this tenant (name + reference code). Use this for broad "
        "'what's going on'/'give me an overview' questions where you don't yet have a "
        "specific customer name to search for."
    ),
    args_schema=ListCustomersArgs,
    handler=_list_customers,
)


class GetTotalOutstandingArgs(BaseModel):
    pass


def _get_total_outstanding(args: GetTotalOutstandingArgs, state: SessionState) -> str:
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


get_total_outstanding_tool = Tool(
    name="get_total_outstanding",
    description=(
        "Total invoiced/paid/outstanding across ALL customers for this tenant. Use this for "
        "'how much overall are we owed' questions, not just one customer."
    ),
    args_schema=GetTotalOutstandingArgs,
    handler=_get_total_outstanding,
)


class ListSuppliersArgs(BaseModel):
    pass


def _list_suppliers(args: ListSuppliersArgs, state: SessionState) -> str:
    suppliers = _supplier_repo.list_all(state.tenant_id)
    if not suppliers:
        return "No suppliers found for this tenant."
    return "\n".join(s.to_llm_readable_output() for s in suppliers)


list_suppliers_tool = Tool(
    name="list_suppliers",
    description=(
        "List every supplier for this tenant (name + reference code). Use this for broad "
        "'what's going on'/'give me an overview' questions where you don't yet have a "
        "specific supplier name to search for."
    ),
    args_schema=ListSuppliersArgs,
    handler=_list_suppliers,
)


class GetSupplierPOsArgs(BaseModel):
    supplier_search: str = Field(
        description="The supplier's reference code (e.g. 'SUP-1043') or name/partial name (e.g. 'Supplier B')."
    )
    status: PurchaseOrderStatus | None = Field(
        default=None, description="Optionally filter to only POs in this status."
    )


def _get_supplier_pos(args: GetSupplierPOsArgs, state: SessionState) -> str:
    try:
        supplier = _supplier_repo.find_one_by_search_term(state.tenant_id, args.supplier_search)
    except ValueError:
        return f"Multiple suppliers match '{args.supplier_search}', be more specific."
    if supplier is None:
        return f"No supplier matching '{args.supplier_search}'."

    pos = _purchase_order_repo.list_by_supplier_reference_code(
        state.tenant_id, supplier.reference_code, args.status
    )
    if not pos:
        return f"No purchase orders found for supplier {supplier.reference_code}."
    return "\n".join(_format_po_with_provenance(po, state) for po in pos)


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


get_supplier_pos_tool = Tool(
    name="get_supplier_pos",
    description="List a supplier's purchase orders, optionally filtered by status.",
    args_schema=GetSupplierPOsArgs,
    handler=_get_supplier_pos,
)


class GetTotalPOQuantityArgs(BaseModel):
    status: PurchaseOrderStatus | None = Field(
        default=None, description="Optionally filter to only POs in this status."
    )


def _get_total_po_quantity(args: GetTotalPOQuantityArgs, state: SessionState) -> str:
    totals = _purchase_order_repo.sum_quantities_for_tenant(state.tenant_id, args.status)
    quantity = totals["quantity"]
    received = totals["received_quantity"]
    pending = quantity - received

    label = f"purchase orders across all suppliers (status={args.status.value})" if args.status else (
        "purchase orders across all suppliers (any status)"
    )
    quantity_tagged = state.provenance.tag("sql", f"total quantity for {label}", quantity)
    received_tagged = state.provenance.tag("sql", f"total received for {label}", received)
    pending_tagged = state.provenance.tag("sql", f"total pending for {label}", pending)
    scope = f"status={args.status.value}" if args.status else "any status"
    return (
        f"Tenant PO totals ({scope}): "
        f"quantity={quantity_tagged}, received={received_tagged}, pending={pending_tagged}. "
        f"Note: purchase orders track quantity/status only, not a monetary amount -- "
        f"there is no ₹ value to total here."
    )


get_total_po_quantity_tool = Tool(
    name="get_total_po_quantity",
    description=(
        "Total PO quantity ordered/received/pending across ALL suppliers, optionally filtered "
        "by status. Purchase orders have no monetary amount in this schema -- use this for "
        "'total units on order' questions, not ₹ value questions."
    ),
    args_schema=GetTotalPOQuantityArgs,
    handler=_get_total_po_quantity,
)


class GetLateOrdersArgs(BaseModel):
    as_of_date: date | None = Field(
        default=None,
        description="Compare promised dates against this date. Defaults to today if omitted.",
    )


def _get_late_orders(args: GetLateOrdersArgs, state: SessionState) -> str:
    as_of = args.as_of_date or date.today()
    orders = _order_repo.list_late(state.tenant_id, as_of)
    if not orders:
        return f"No late orders as of {as_of.isoformat()}."
    return "\n".join(order.to_llm_readable_output() for order in orders)


get_late_orders_tool = Tool(
    name="get_late_orders",
    description=(
        "List every order that is not delivered/cancelled and whose promised date has "
        "already passed."
    ),
    args_schema=GetLateOrdersArgs,
    handler=_get_late_orders,
)

SQL_TOOLS = [
    get_customer_outstanding_tool,
    get_supplier_pos_tool,
    get_late_orders_tool,
    list_customers_tool,
    list_suppliers_tool,
    list_invoices_tool,
    get_total_outstanding_tool,
    get_total_po_quantity_tool,
]
