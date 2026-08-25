"""Seeds tenant A's ERP data + a handful of reviewed knowledge_base rows.

Run with: python db/seed_tenant_a.py

Hand-authored anchor rows mirror the PDF's own examples exactly (see
README.md's "Seed data snapshot") so demo queries can echo the
explainer almost verbatim -- everything else is generated filler that
makes the tenant look like a real, populated business.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `python db/seed_tenant_a.py` finds app/, db/

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

TENANT_ID = "tenant_a"


def main() -> None:
    wipe_tenant(TENANT_ID)

    # --- Anchor rows: mirror the explainer PDF's own examples exactly ---
    supplier_b_id = insert_supplier(TENANT_ID, "SUP-1043", "Supplier B Ltd.")
    supplier_c_id = insert_supplier(TENANT_ID, "SUP-1099", "Supplier C")
    sharma_id = insert_customer(TENANT_ID, "CUST-0078", "Sharma Fabrics")

    # PO-4812: ERP says open, full quantity, due Tuesday -- a chat message
    # (seeded in chat_data/tenant_a_messages.json) says it was actually
    # partially received. That mismatch is the flat contradiction case.
    po_4812_id = insert_purchase_order(
        TENANT_ID,
        "PO-4812",
        supplier_b_id,
        status="open",
        quantity=1000,
        received_quantity=1000,
        due_date=date(2024, 5, 21),  # Tuesday
    )

    # Supplier C: open POs, zero chat mentions -- the absence-of-evidence case.
    insert_purchase_order(
        TENANT_ID, "PO-4820", supplier_c_id, status="open", quantity=600, received_quantity=0,
        due_date=date(2024, 6, 3),
    )

    # INV-2201: fully outstanding (no payments) -- a chat message claims
    # part of it ("80k") is disputed. That's the number-with-qualifier case.
    insert_invoice(TENANT_ID, "INV-2201", sharma_id, amount=420_000)

    # --- Generated filler: makes tenant A look like a populated business.
    # Anchor rows (Sharma, PO-4812/PO-4820, INV-2201) are deliberately left
    # out of every generator pool below -- the demo examples in README.md
    # depend on Sharma's outstanding being exactly 420000 and Supplier B/C's
    # PO lists being exactly what's asserted above, so nothing generated
    # is allowed to add more rows onto those specific anchors. ---
    supplier_ids = generate_suppliers(TENANT_ID, count=15, name_shuffle_seed=1)
    customer_ids = generate_customers(TENANT_ID, count=15, name_shuffle_seed=2, exclude_names={"Sharma Fabrics"})
    generate_purchase_orders(TENANT_ID, list(supplier_ids.values()), count=35, seed=3)
    generate_orders(TENANT_ID, list(customer_ids.values()), count=35, seed=4)
    generate_invoices_with_payments(TENANT_ID, list(customer_ids.values()), count=25, seed=5)
    inventory_ids = generate_inventory(TENANT_ID, seed=6)

    # --- Entity-linking knowledge: the curated, trusted bridge Phase 3's
    # resolve_entity looks up first. Both aliases point at the same
    # supplier so either informal phrasing resolves deterministically. ---
    insert_knowledge_base_row(TENANT_ID, "supp B", "supplier", supplier_b_id, source="reviewed")
    insert_knowledge_base_row(TENANT_ID, "Supplier B", "supplier", supplier_b_id, source="reviewed")
    # Chat writes the bare digits people actually type ("4812"), not the full "PO-4812".
    insert_knowledge_base_row(TENANT_ID, "4812", "purchase_order", po_4812_id, source="reviewed")

    # Tenant vocabulary drift setup: tenant A calls a batch of stock a
    # "lot" -- tenant B's seed script maps the same concept to "batch".
    insert_knowledge_base_row(
        TENANT_ID, "lot", "inventory_item", inventory_ids["DYE-BLU-40"], source="reviewed"
    )

    print(f"Seeded {TENANT_ID}: 3 anchor suppliers/customers, PO-4812, PO-4820, INV-2201, "
          f"{len(supplier_ids)} generated suppliers, {len(customer_ids)} generated customers, "
          f"35 purchase orders, 35 orders, 25 invoices, {len(inventory_ids)} inventory items, "
          f"4 knowledge_base rows.")


if __name__ == "__main__":
    main()

    from app.db import close_pool

    close_pool()
