"""Generates the raw WhatsApp-style message JSON files chat search reads.

Run with: python chat_data/generate_messages.py (after seeding both
tenants' ERP data -- it pulls real reference codes/names out of Postgres
so generated chatter references entities that actually exist).

Writes `chat_data/tenant_a_messages.json` and `chat_data/tenant_b_messages.json`.
Each tenant's file opens with the explainer PDF's own example lines,
verbatim, paired with the anchor ERP rows `db/seed_tenant_a.py` /
`db/seed_tenant_b.py` create -- everything after that is templated
filler chatter referencing real supplier/customer/PO names+codes, so
`search_messages` has enough volume to make top-k results meaningful.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import close_pool, run_query

_SENDERS = ["Ramesh", "Priya", "Anil", "Sunita", "Vikram", "Deepa"]

_TEMPLATES_WITH_SUPPLIER = [
    "{supplier} pushing delivery by a week",
    "checking with {supplier} about status, no reply yet",
    "{supplier} confirmed pickup for tomorrow",
    "any update from {supplier} on the pending order?",
    "{supplier} says there's a delay at their end",
]

_TEMPLATES_WITH_PO = [
    "any update on {po}?",
    "{po} status check, need it urgently",
    "confirmed with warehouse, {po} not fully in yet",
    "following up on {po} again today",
]

_TEMPLATES_WITH_CUSTOMER = [
    "{customer} asking for an extension on payment",
    "{customer} confirmed order received, all good",
    "spoke to {customer}, they'll pay by Friday",
    "{customer} wants to increase next order size",
]

_TEMPLATES_WITH_ITEM = [
    "{item} running low in stock",
    "need more {item} urgently for the next batch",
    "{item} delivery expected Monday",
    "check {item} stock before confirming new orders",
]

_TEMPLATES_GENERIC = [
    "good morning team",
    "let's sync at 3pm today",
    "sending photos of the shipment shortly",
    "dyeing line down since morning",
    "power cut in the unit, back up in an hour",
    "please confirm attendance for tomorrow's stock count",
    "invoice copies shared in the drive folder",
    "reminder: month-end closing this Friday",
]


def _fetch(tenant_id: str, table: str, columns: str) -> list[dict]:
    return run_query(f"SELECT {columns} FROM {table} WHERE tenant_id = %s", (tenant_id,))


def _generate_filler(
    tenant_id: str, suppliers: list[dict], customers: list[dict],
    purchase_orders: list[dict], items: list[dict], start_id: int, count: int, seed: int,
    start_time: datetime,
) -> list[dict]:
    rng = random.Random(seed)
    messages: list[dict] = []
    when = start_time
    for i in range(count):
        when = when + timedelta(hours=rng.randint(1, 6))
        bucket = rng.choice(["supplier", "po", "customer", "item", "generic"])
        if bucket == "supplier" and suppliers:
            supplier = rng.choice(suppliers)
            text = rng.choice(_TEMPLATES_WITH_SUPPLIER).format(supplier=supplier["name"])
        elif bucket == "po" and purchase_orders:
            po = rng.choice(purchase_orders)
            # Chat uses the bare digits people actually type, e.g. "4812" not "PO-4812".
            text = rng.choice(_TEMPLATES_WITH_PO).format(po=po["reference_code"].split("-")[-1])
        elif bucket == "customer" and customers:
            customer = rng.choice(customers)
            text = rng.choice(_TEMPLATES_WITH_CUSTOMER).format(customer=customer["name"])
        elif bucket == "item" and items:
            item = rng.choice(items)
            text = rng.choice(_TEMPLATES_WITH_ITEM).format(item=item["description"].split(",")[0])
        else:
            text = rng.choice(_TEMPLATES_GENERIC)

        messages.append(
            {
                "message_id": f"msg_{start_id + i:03d}",
                "tenant_id": tenant_id,
                "sender": rng.choice(_SENDERS),
                "timestamp": when.isoformat(),
                "text": text,
            }
        )
    return messages


def build_tenant_a() -> list[dict]:
    anchors = [
        {
            "message_id": "msg_001", "tenant_id": "tenant_a", "sender": "Ramesh",
            "timestamp": "2024-05-14T09:02:00", "text": "Sharma disputing 80k, says short supply",
        },
        {
            "message_id": "msg_002", "tenant_id": "tenant_a", "sender": "Priya",
            "timestamp": "2024-05-17T11:30:00", "text": "4812 partially received, 300 units short",
        },
        {
            "message_id": "msg_003", "tenant_id": "tenant_a", "sender": "Priya",
            "timestamp": "2024-05-19T14:00:00", "text": "supp B pushing delivery by a week",
        },
    ]
    suppliers = _fetch("tenant_a", "suppliers", "reference_code, name")
    customers = _fetch("tenant_a", "customers", "reference_code, name")
    pos = _fetch("tenant_a", "purchase_orders", "reference_code")
    items = _fetch("tenant_a", "inventory", "description")
    filler = _generate_filler(
        "tenant_a", suppliers, customers, pos, items,
        start_id=4, count=120, seed=101, start_time=datetime(2024, 5, 19, 15, 0),
    )
    return anchors + filler


def build_tenant_b() -> list[dict]:
    anchors = [
        {
            "message_id": "msg_001", "tenant_id": "tenant_b", "sender": "Anil",
            "timestamp": "2024-05-21T10:15:00", "text": "Verma disputing 60k, says goods damaged",
        },
        {
            "message_id": "msg_002", "tenant_id": "tenant_b", "sender": "Sunita",
            "timestamp": "2024-05-24T13:45:00", "text": "5812 partially received, 200 units short",
        },
        {
            "message_id": "msg_003", "tenant_id": "tenant_b", "sender": "Sunita",
            "timestamp": "2024-05-26T09:30:00", "text": "ColorTech pushing delivery by a week",
        },
    ]
    suppliers = _fetch("tenant_b", "suppliers", "reference_code, name")
    customers = _fetch("tenant_b", "customers", "reference_code, name")
    pos = _fetch("tenant_b", "purchase_orders", "reference_code")
    items = _fetch("tenant_b", "inventory", "description")
    filler = _generate_filler(
        "tenant_b", suppliers, customers, pos, items,
        start_id=4, count=120, seed=201, start_time=datetime(2024, 5, 26, 10, 0),
    )
    return anchors + filler


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    tenant_a_messages = build_tenant_a()
    tenant_b_messages = build_tenant_b()

    (out_dir / "tenant_a_messages.json").write_text(json.dumps(tenant_a_messages, indent=2))
    (out_dir / "tenant_b_messages.json").write_text(json.dumps(tenant_b_messages, indent=2))
    print(f"Wrote {len(tenant_a_messages)} tenant_a messages, {len(tenant_b_messages)} tenant_b messages.")

    close_pool()


if __name__ == "__main__":
    main()
