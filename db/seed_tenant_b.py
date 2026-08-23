"""Seeds tenant B's ERP data + a handful of reviewed knowledge_base rows.

Run with: python db/seed_tenant_b.py

Deliberately mirrors tenant A's shape (a contradiction case, a
number-with-qualifier case, an absence-of-evidence case) but with its
own names/codes/amounts, plus the other half of the tenant-vocabulary
setup: tenant A calls it a "lot", tenant B calls the same kind of
thing a "batch" -- proving entity linking doesn't fork per tenant.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `python db/seed_tenant_b.py` finds app/, db/

from db.seed_common import (
    generate_customers,
    generate_inventory,
    generate_invoices_with_payments,
    generate_orders,
    generate_purchase_orders,
    generate_suppliers,
    insert_customer,
    insert_invoice,
    insert_knowledge_base_row,
    insert_purchase_order,
    insert_supplier,
    wipe_tenant,
)

TENANT_ID = "tenant_b"


def main() -> None:
    wipe_tenant(TENANT_ID)

    # --- Anchor rows: tenant B's own contradiction / qualifier / absence cases ---
    colortech_id = insert_supplier(TENANT_ID, "SUP-2043", "ColorTech Dyers")
    northstar_id = insert_supplier(TENANT_ID, "SUP-2099", "NorthStar Yarns")
    verma_id = insert_customer(TENANT_ID, "CUST-1078", "Verma Garments")

    # PO-5812: ERP says open, full quantity -- a chat message (seeded in
    # chat_data/tenant_b_messages.json) says it was actually partially
    # received. Same flat-contradiction shape as tenant A's PO-4812.
    po_5812_id = insert_purchase_order(
        TENANT_ID, "PO-5812", colortech_id, status="open", quantity=800, received_quantity=800,
        due_date=date(2024, 5, 28),  # Tuesday
    )

    # NorthStar Yarns: open PO, zero chat mentions -- the absence-of-evidence case.
    insert_purchase_order(
        TENANT_ID, "PO-5820", northstar_id, status="open", quantity=450, received_quantity=0,
        due_date=date(2024, 6, 10),
    )

    # INV-3201: fully outstanding (no payments) -- a chat message disputes
    # part of it. Same number-with-qualifier shape as tenant A's INV-2201.
    insert_invoice(TENANT_ID, "INV-3201", verma_id, amount=275_000)

    # --- Generated filler: makes tenant B look like a populated business.
    # Anchors (Verma, PO-5812/PO-5820, INV-3201) stay out of every
    # generator pool below, for the same reason as tenant A: the demo
    # examples depend on their exact numbers, so nothing generated may
    # silently pile additional rows onto them. ---
    supplier_ids = generate_suppliers(TENANT_ID, count=15, name_shuffle_seed=11)
    customer_ids = generate_customers(TENANT_ID, count=15, name_shuffle_seed=12, exclude_names={"Verma Garments"})
    generate_purchase_orders(TENANT_ID, list(supplier_ids.values()), count=35, seed=13)
    generate_orders(TENANT_ID, list(customer_ids.values()), count=35, seed=14)
    generate_invoices_with_payments(TENANT_ID, list(customer_ids.values()), count=25, seed=15)
    inventory_ids = generate_inventory(TENANT_ID, seed=16)

    # --- Entity-linking knowledge: the curated, trusted bridge Phase 3's
    # resolve_entity looks up first. ---
    insert_knowledge_base_row(TENANT_ID, "ColorTech", "supplier", colortech_id, source="reviewed")
    insert_knowledge_base_row(TENANT_ID, "the dye guys", "supplier", colortech_id, source="reviewed")
    # Chat writes the bare digits people actually type ("5812"), not the full "PO-5812".
    insert_knowledge_base_row(TENANT_ID, "5812", "purchase_order", po_5812_id, source="reviewed")

    # Tenant vocabulary drift: tenant B calls the same kind of stock a
    # "batch" where tenant A (seed_tenant_a.py) calls it a "lot".
    insert_knowledge_base_row(
        TENANT_ID, "batch", "inventory_item", inventory_ids["DYE-BLU-40"], source="reviewed"
    )

    print(f"Seeded {TENANT_ID}: 3 anchor suppliers/customers, PO-5812, PO-5820, INV-3201, "
          f"{len(supplier_ids)} generated suppliers, {len(customer_ids)} generated customers, "
          f"35 purchase orders, 35 orders, 25 invoices, {len(inventory_ids)} inventory items, "
          f"4 knowledge_base rows.")


if __name__ == "__main__":
    main()

    from app.db import close_pool

    close_pool()
