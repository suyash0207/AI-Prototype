"""Shared generation + insert helpers used by both tenant seed scripts.

Kept here so `seed_tenant_a.py` and `seed_tenant_b.py` only need to
supply *what's different* about their tenant (the anchor rows, the
vocabulary word) -- the mechanics of "insert N randomish suppliers"
are identical for both and shouldn't be copy-pasted twice.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.db import get_pool

_SUPPLIER_NAMES = [
    "Radha Textiles",
    "Om Dyeworks",
    "Krishna Yarns",
    "Ganesh Fabrics",
    "Bharat Weaving Co",
    "Shiva Cotton Mills",
    "Laxmi Threads",
    "Vishnu Chemicals",
    "Annapurna Dyers",
    "Surya Textiles",
    "Ashoka Fibres",
    "Ganga Spinners",
    "Himalaya Dye Works",
    "Indus Cotton",
    "Jai Bharat Yarns",
    "Kaveri Fabrics",
    "Malabar Weaves",
    "Narmada Textiles",
    "Prakash Dyers",
    "Sundaram Mills",
]

_CUSTOMER_NAMES = [
    "Sharma Fabrics",
    "Verma Garments",
    "Gupta Textiles",
    "Iyer Exports",
    "Patel Clothing",
    "Reddy Apparel",
    "Chopra Fashions",
    "Nair Garments",
    "Mehta Textiles",
    "Joshi Exports",
    "Kumar Apparel",
    "Singh Fabrics",
    "Rao Clothing",
    "Desai Garments",
    "Bose Textiles",
    "Kapoor Exports",
    "Agarwal Fashions",
    "Menon Apparel",
    "Saxena Fabrics",
    "Pillai Garments",
]

_INVENTORY_ITEMS = [
    ("DYE-BLU-40", "Blue dye, 40kg drum"),
    ("DYE-RED-40", "Red dye, 40kg drum"),
    ("YRN-CTN-100", "Cotton yarn, 100kg bale"),
    ("YRN-POL-100", "Polyester yarn, 100kg bale"),
    ("FAB-DEN-50", "Denim fabric, 50m roll"),
    ("FAB-SLK-30", "Silk fabric, 30m roll"),
    ("CHM-STR-25", "Starch chemical, 25kg sack"),
    ("CHM-SFT-25", "Softener chemical, 25kg sack"),
]

_PURCHASE_ORDER_STATUSES = ["open", "partially_received", "received", "cancelled"]
_ORDER_STATUSES = ["pending", "shipped", "delayed", "delivered", "cancelled"]


@dataclass
class SeededIds:
    """UUIDs of rows the caller explicitly created by reference_code, so
    seed scripts can wire up knowledge_base rows / anchor purchase orders
    /invoices without re-querying the database.
    """

    supplier_ids: dict[str, str] = field(default_factory=dict)
    customer_ids: dict[str, str] = field(default_factory=dict)
    inventory_ids: dict[str, str] = field(default_factory=dict)


def wipe_tenant(tenant_id: str) -> None:
    """Delete every row for this tenant so the seed script can be re-run
    from a clean slate without hand-truncating tables first.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM payments WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM invoices WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM orders WHERE tenant_id = %s", (tenant_id,))
            cur.execute(
                "DELETE FROM purchase_orders WHERE tenant_id = %s", (tenant_id,)
            )
            cur.execute("DELETE FROM inventory WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM knowledge_base WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM customers WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM suppliers WHERE tenant_id = %s", (tenant_id,))
        conn.commit()


def insert_supplier(tenant_id: str, reference_code: str, name: str) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO suppliers (tenant_id, reference_code, name) VALUES (%s, %s, %s) RETURNING id",
                (tenant_id, reference_code, name),
            )
            supplier_id = cur.fetchone()[0]
        conn.commit()
    return str(supplier_id)


def insert_customer(tenant_id: str, reference_code: str, name: str) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO customers (tenant_id, reference_code, name) VALUES (%s, %s, %s) RETURNING id",
                (tenant_id, reference_code, name),
            )
            customer_id = cur.fetchone()[0]
        conn.commit()
    return str(customer_id)


def insert_inventory_item(
    tenant_id: str, sku: str, description: str, quantity: int
) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO inventory (tenant_id, sku, description, quantity) VALUES (%s, %s, %s, %s) "
                "RETURNING id",
                (tenant_id, sku, description, quantity),
            )
            item_id = cur.fetchone()[0]
        conn.commit()
    return str(item_id)


def insert_purchase_order(
    tenant_id: str,
    reference_code: str,
    supplier_id: str,
    status: str,
    quantity: int,
    received_quantity: int,
    due_date: date | None,
) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO purchase_orders "
                "(tenant_id, reference_code, supplier_id, status, quantity, received_quantity, due_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    tenant_id,
                    reference_code,
                    supplier_id,
                    status,
                    quantity,
                    received_quantity,
                    due_date,
                ),
            )
            po_id = cur.fetchone()[0]
        conn.commit()
    return str(po_id)


def insert_order(
    tenant_id: str,
    reference_code: str,
    customer_id: str,
    status: str,
    promised_date: date | None,
) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (tenant_id, reference_code, customer_id, status, promised_date) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (tenant_id, reference_code, customer_id, status, promised_date),
            )
            order_id = cur.fetchone()[0]
        conn.commit()
    return str(order_id)


def insert_invoice(
    tenant_id: str, reference_code: str, customer_id: str, amount: float
) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO invoices (tenant_id, reference_code, customer_id, amount) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (tenant_id, reference_code, customer_id, amount),
            )
            invoice_id = cur.fetchone()[0]
        conn.commit()
    return str(invoice_id)


def insert_payment(
    tenant_id: str, invoice_id: str, amount: float, paid_at: datetime
) -> None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO payments (tenant_id, invoice_id, amount, paid_at) VALUES (%s, %s, %s, %s)",
                (tenant_id, invoice_id, amount, paid_at),
            )
        conn.commit()


def insert_knowledge_base_row(
    tenant_id: str,
    alias_text: str,
    canonical_type: str,
    canonical_id: str,
    source: str = "reviewed",
    confidence: float = 1.0,
) -> None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO knowledge_base "
                "(tenant_id, alias_text, canonical_type, canonical_id, confidence, source) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    tenant_id,
                    alias_text,
                    canonical_type,
                    canonical_id,
                    confidence,
                    source,
                ),
            )
        conn.commit()


def generate_suppliers(
    tenant_id: str, count: int, name_shuffle_seed: int
) -> dict[str, str]:
    """Insert `count` generated suppliers (reference codes SUP-2000+),
    returning {reference_code: id}. Anchors are inserted separately by
    the caller with their own fixed reference_codes so this never
    collides with them.
    """
    rng = random.Random(name_shuffle_seed)
    names = rng.sample(_SUPPLIER_NAMES, k=min(count, len(_SUPPLIER_NAMES)))
    result: dict[str, str] = {}
    for i, name in enumerate(names):
        reference_code = f"SUP-{2000 + i}"
        result[reference_code] = insert_supplier(tenant_id, reference_code, name)
    return result


def generate_customers(
    tenant_id: str,
    count: int,
    name_shuffle_seed: int,
    exclude_names: set[str] | None = None,
) -> dict[str, str]:
    """`exclude_names` keeps generated filler from accidentally duplicating
    an anchor customer's name (e.g. "Sharma Fabrics") -- a name collision
    would make `find_one_by_search_term`'s partial-name match ambiguous
    and break the exact demo query the anchor exists to support.
    """
    rng = random.Random(name_shuffle_seed)
    pool = [n for n in _CUSTOMER_NAMES if n not in (exclude_names or set())]
    names = rng.sample(pool, k=min(count, len(pool)))
    result: dict[str, str] = {}
    for i, name in enumerate(names):
        reference_code = f"CUST-{2000 + i}"
        result[reference_code] = insert_customer(tenant_id, reference_code, name)
    return result


def generate_purchase_orders(
    tenant_id: str,
    supplier_ids: list[str],
    count: int,
    seed: int,
    start_code: int = 5000,
) -> None:
    rng = random.Random(seed)
    today = date.today()
    for i in range(count):
        supplier_id = rng.choice(supplier_ids)
        status = rng.choice(_PURCHASE_ORDER_STATUSES)
        quantity = rng.randint(50, 2000)
        received_quantity = (
            quantity if status == "received" else rng.randint(0, quantity)
        )
        due_date = today + timedelta(days=rng.randint(-30, 30))
        insert_purchase_order(
            tenant_id,
            f"PO-{start_code + i}",
            supplier_id,
            status,
            quantity,
            received_quantity,
            due_date,
        )


def generate_orders(
    tenant_id: str,
    customer_ids: list[str],
    count: int,
    seed: int,
    start_code: int = 3000,
) -> None:
    rng = random.Random(seed)
    today = date.today()
    for i in range(count):
        customer_id = rng.choice(customer_ids)
        status = rng.choice(_ORDER_STATUSES)
        promised_date = today + timedelta(days=rng.randint(-30, 30))
        insert_order(
            tenant_id, f"ORD-{start_code + i}", customer_id, status, promised_date
        )


def generate_invoices_with_payments(
    tenant_id: str,
    customer_ids: list[str],
    count: int,
    seed: int,
    start_code: int = 9000,
) -> None:
    rng = random.Random(seed)
    now = datetime.now()
    for i in range(count):
        customer_id = rng.choice(customer_ids)
        amount = round(rng.uniform(5_000, 500_000), 2)
        invoice_id = insert_invoice(
            tenant_id, f"INV-{start_code + i}", customer_id, amount
        )
        if rng.random() < 0.6:
            paid_amount = round(amount * rng.uniform(0.3, 1.0), 2)
            insert_payment(
                tenant_id,
                invoice_id,
                paid_amount,
                now - timedelta(days=rng.randint(1, 60)),
            )


def generate_inventory(tenant_id: str, seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    result: dict[str, str] = {}
    for sku, description in _INVENTORY_ITEMS:
        quantity = rng.randint(10, 500)
        result[sku] = insert_inventory_item(tenant_id, sku, description, quantity)
    return result
