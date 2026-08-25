"""Status/type vocabularies shared by the schema, entities, and tools.

Plain `str, Enum` classes so a member serializes as its raw string value
and compares equal to whatever `app/db.py` reads back from Postgres --
no separate mapping step between "the DB's word for it" and "Python's
word for it".
"""

from enum import Enum


class PurchaseOrderStatus(str, Enum):
    """Where a purchase order (an order we placed with a supplier) currently stands."""

    OPEN = "open"                              # placed, nothing has arrived yet
    PARTIALLY_RECEIVED = "partially_received"   # some units arrived, but not all
    RECEIVED = "received"                       # everything we ordered has arrived
    CANCELLED = "cancelled"                     # the order was called off


class OrderStatus(str, Enum):
    """Where a customer's order currently stands."""

    PENDING = "pending"       # placed, not yet on its way
    SHIPPED = "shipped"       # on its way to the customer
    DELAYED = "delayed"       # running later than promised
    DELIVERED = "delivered"   # customer has received it
    CANCELLED = "cancelled"   # the order was called off


class CanonicalEntityType(str, Enum):
    """Which kind of ERP record a knowledge_base row's canonical_id points at."""

    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PURCHASE_ORDER = "purchase_order"
    ORDER = "order"
    INVENTORY_ITEM = "inventory_item"


class KnowledgeSource(str, Enum):
    """How a chat-to-ERP name mapping came to exist.

    Only three values, not four: a `seed` value would just mean
    "reviewed, but before the system existed" -- no code path treats
    it any differently from `reviewed` (both are fully trusted, used
    deterministically, never re-questioned). Hand-authored seed rows
    just write source=REVIEWED directly.
    """

    REVIEWED = "reviewed"              # a human (including whoever set up the demo data) vouched for it
    LLM_SUGGESTED = "llm_suggested"    # the model proposed it, not yet confirmed by a person
    USER_CONFIRMED = "user_confirmed"  # a user picked this from an ask_clarification question
