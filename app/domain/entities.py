"""Typed, printable domain objects.

One Pydantic model per ERP table (plus a couple of pure value objects
that aren't backed by any table). Every entity derives from
`LLMReadableEntity`, so any tool that needs to hand a result to the
model can call the exact same method regardless of which concrete
entity it's holding -- the "how do we print this to the model"
question only ever gets answered once per concept, not once per tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import (
    CanonicalEntityType,
    KnowledgeSource,
    OrderStatus,
    PurchaseOrderStatus,
)


class LLMReadableEntity(BaseModel, ABC):
    """Base for anything we're willing to hand to the model as text."""

    @abstractmethod
    def to_llm_readable_output(self) -> str:
        """Turn this into a plain-English line the model can read directly."""
        ...


class Supplier(LLMReadableEntity):
    """A company that sells us raw materials -- we buy things from suppliers."""

    id: UUID  # random unique id, internal only
    tenant_id: str  # which business this belongs to
    reference_code: str  # short id people say out loud, e.g. "SUP-1043"
    name: str  # full name, e.g. "Supplier B Ltd."

    def to_llm_readable_output(self) -> str:
        return f"Supplier {self.name} ({self.reference_code})"


class Customer(LLMReadableEntity):
    """A company that buys goods from us -- we sell things to customers."""

    id: UUID
    tenant_id: str
    reference_code: str  # e.g. "CUST-0078"
    name: str  # e.g. "Sharma Fabrics"

    def to_llm_readable_output(self) -> str:
        return f"Customer {self.name} ({self.reference_code})"


class PurchaseOrder(LLMReadableEntity):
    """An order we placed with a supplier to buy goods, and how much has arrived so far."""

    id: UUID  # random unique id, internal only
    tenant_id: str  # which business this belongs to
    reference_code: str  # short id people say out loud, e.g. "PO-4812"
    supplier_id: UUID  # which supplier this order was placed with
    status: PurchaseOrderStatus  # where the order stands right now
    quantity: int  # how many units we ordered in total
    received_quantity: int  # how many units have actually shown up so far
    due_date: date | None  # the date the supplier promised delivery by
    created_at: datetime

    def to_llm_readable_output(self) -> str:
        due = self.due_date.isoformat() if self.due_date else "unspecified"
        return (
            f"PO {self.reference_code}: status={self.status.value}, "
            f"quantity={self.quantity}, received={self.received_quantity}, "
            f"due={due}"
        )


class Order(LLMReadableEntity):
    """An order a customer placed with us to buy goods, and whether we've shipped it."""

    id: UUID
    tenant_id: str
    reference_code: str  # e.g. "ORD-2201"
    customer_id: UUID  # which customer placed this order
    status: OrderStatus  # where the order stands right now
    promised_date: date | None  # the date we told the customer to expect it
    created_at: datetime

    def to_llm_readable_output(self) -> str:
        promised = (
            self.promised_date.isoformat() if self.promised_date else "unspecified"
        )
        return f"Order {self.reference_code}: status={self.status.value}, promised={promised}"


class Invoice(LLMReadableEntity):
    """A bill we sent a customer for goods they bought -- what they owe us."""

    id: UUID
    tenant_id: str
    reference_code: str  # e.g. "INV-9931"
    customer_id: UUID  # which customer this bill was sent to
    amount: float  # the total amount billed on this invoice
    created_at: datetime

    def to_llm_readable_output(self) -> str:
        return f"Invoice {self.reference_code}: amount={self.amount}"


class Payment(LLMReadableEntity):
    """Money a customer actually paid against one of our invoices."""

    id: UUID
    tenant_id: str
    invoice_id: UUID  # which invoice this payment was made against
    amount: float  # how much was paid in this one payment
    paid_at: datetime

    def to_llm_readable_output(self) -> str:
        return f"Payment of {self.amount} on {self.paid_at.date().isoformat()}"


class InventoryItem(LLMReadableEntity):
    """Raw materials or goods physically sitting in our warehouse right now."""

    id: UUID
    tenant_id: str
    sku: str  # the stock-keeping code for this item, e.g. "DYE-BLU-40"
    description: str  # plain-English name of the item, e.g. "Blue dye, 40kg drum"
    quantity: int  # how many units of this item we currently have on hand

    def to_llm_readable_output(self) -> str:
        return f"{self.description} ({self.sku}): quantity={self.quantity}"


class CustomerOutstanding(LLMReadableEntity):
    """How much a customer owes us right now (invoiced minus paid).

    Not backed by its own table -- it's a computed summary over
    `invoices` and `payments`, only ever produced by a repository
    query, never stored.
    """

    customer: Customer
    invoiced: float  # sum of that customer's invoice amounts
    paid: float  # sum of that customer's payment amounts
    outstanding: float  # invoiced - paid

    def to_llm_readable_output(self) -> str:
        return (
            f"{self.customer.name} ({self.customer.reference_code}): "
            f"invoiced={self.invoiced}, paid={self.paid}, outstanding={self.outstanding}"
        )


class KnowledgeBaseEntry(LLMReadableEntity):
    """A learned or confirmed mapping from an informal chat name to an exact ERP record.

    e.g. chat says "Supplier B" or "supp B" -- this row says that means SUP-1043.
    """

    id: UUID
    tenant_id: str
    alias_text: str  # the informal phrase as written in chat, e.g. "supp B"
    canonical_type: CanonicalEntityType  # which kind of ERP record this points to
    canonical_id: UUID  # the id of that exact ERP record
    confidence: float  # how sure we are this mapping is correct, 0 to 1
    source: KnowledgeSource  # how this mapping came to exist

    def to_llm_readable_output(self) -> str:
        return (
            f"'{self.alias_text}' -> {self.canonical_type.value}:{self.canonical_id} "
            f"(confidence={self.confidence}, source={self.source.value})"
        )


class ChatClaim(LLMReadableEntity):
    """One fact the retrieval sub-agent pulled out of a chat message.

    Ephemeral -- not backed by any table. This is the retrieval
    sub-agent's `return_claims` return shape: a structured fact, never
    a prose summary, so the orchestrator can register it into the
    provenance ledger and later cross-check it against SQL.
    """

    message_ref: (
        str  # which chat message this claim came from, e.g. "msg:tenant_a:0042"
    )
    sender: str  # who sent that message
    timestamp: datetime  # when that message was sent
    extracted_claim: str  # the plain-English fact pulled out of the message
    linked_entity: str | None = (
        None  # resolved reference_code this claim is about, if any (e.g. "SUP-1043")
    )

    def to_llm_readable_output(self) -> str:
        entity = self.linked_entity or "unlinked"
        return (
            f"[{self.message_ref}] {self.sender} ({self.timestamp.isoformat()}): "
            f"{self.extracted_claim} (entity={entity})"
        )
