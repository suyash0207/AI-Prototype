"""The entity-linking bridge: `resolve_entity` turns an informal mention
("supp B", "4812", "the blue thread guys") into a canonical ERP record
-- without ever letting a wrong guess silently corrupt a figure.

Step 1 (deterministic, trusted): exact lookup against `knowledge_base`,
filtered to reviewed/user_confirmed rows only. A hit here is safe to
use immediately -- no LLM judgment involved.

Step 2+3 (deterministic fuzzy fallback): if nothing trusted matches,
score every supplier/customer/purchase_order/inventory_item in the
tenant by string similarity to the mention, then classify the result
as resolved/ambiguous/unresolved via a fixed threshold + margin check.
This classification is plain code, not an LLM call -- "LLM-assisted"
in the plan refers to the *calling* agent's own judgment over these
scores (materiality, step 4), not a second model call hidden inside
this tool.

Crucially: even a "resolved" classification is not trusted silently.
No code path here writes to `knowledge_base` -- that only happens via
`confirm_entity_link`, once a person has actually said yes.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from uuid import UUID

from pydantic import BaseModel, Field

from app.db import run_query
from app.domain.enums import CanonicalEntityType
from app.repositories.customer_repository import CustomerRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.supplier_repository import SupplierRepository
from app.state.session_state import SessionState
from app.tools.base import Tool

_knowledge_repo = KnowledgeBaseRepository()
_supplier_repo = SupplierRepository()
_customer_repo = CustomerRepository()
_inventory_repo = InventoryRepository()
_purchase_order_repo = PurchaseOrderRepository()

# A "resolved" classification needs the top candidate at/above this score,
# AND a clear enough gap over the runner-up -- both hardcoded, deterministic
# cutoffs, not model judgment. Tuned loose enough to catch typos/shorthand
# ("supp B", "4812") without being so loose it treats an unrelated name as
# a near-miss.
_RESOLVED_THRESHOLD = 0.55
_MARGIN_THRESHOLD = 0.15
_MAX_CANDIDATES_SHOWN = 5

# How close a mention has to be to an *already-trusted* alias_text (not a
# raw ERP name) to still count as step 1's deterministic lookup rather
# than a step-2 fresh guess. Much stricter than _RESOLVED_THRESHOLD --
# this only forgives minor phrasing noise ("the dye guys" vs "dye guys",
# a trailing "'s"), it never lets a genuinely different phrase borrow an
# existing alias's trust.
_TRUSTED_FUZZY_THRESHOLD = 0.75


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _candidates_for_tenant(tenant_id: str, mention: str) -> list[dict]:
    """Deterministic fuzzy candidate generation across every table a
    knowledge_base row could point at. Lives here, not in a repository,
    because it composes across multiple aggregates -- that's application
    logic (entity linking), not a single aggregate's row<->entity mapping.
    """
    candidates: list[dict] = []

    for row in run_query("SELECT id, reference_code, name FROM suppliers WHERE tenant_id = %s", (tenant_id,)):
        candidates.append(
            {
                "canonical_type": CanonicalEntityType.SUPPLIER,
                "canonical_id": row["id"],
                "reference_code": row["reference_code"],
                "label": row["name"],
                "confidence": max(_similarity(mention, row["name"]), _similarity(mention, row["reference_code"])),
            }
        )

    for row in run_query("SELECT id, reference_code, name FROM customers WHERE tenant_id = %s", (tenant_id,)):
        candidates.append(
            {
                "canonical_type": CanonicalEntityType.CUSTOMER,
                "canonical_id": row["id"],
                "reference_code": row["reference_code"],
                "label": row["name"],
                "confidence": max(_similarity(mention, row["name"]), _similarity(mention, row["reference_code"])),
            }
        )

    for row in run_query("SELECT id, reference_code FROM purchase_orders WHERE tenant_id = %s", (tenant_id,)):
        bare_digits = row["reference_code"].split("-")[-1]
        candidates.append(
            {
                "canonical_type": CanonicalEntityType.PURCHASE_ORDER,
                "canonical_id": row["id"],
                "reference_code": row["reference_code"],
                "label": row["reference_code"],
                "confidence": max(_similarity(mention, row["reference_code"]), _similarity(mention, bare_digits)),
            }
        )

    for row in run_query("SELECT id, sku, description FROM inventory WHERE tenant_id = %s", (tenant_id,)):
        candidates.append(
            {
                "canonical_type": CanonicalEntityType.INVENTORY_ITEM,
                "canonical_id": row["id"],
                "reference_code": row["sku"],
                "label": row["description"],
                "confidence": max(_similarity(mention, row["description"]), _similarity(mention, row["sku"])),
            }
        )

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates


class ResolveEntityArgs(BaseModel):
    mention: str = Field(
        description="The informal phrase to link, e.g. 'supp B', '4812', or 'the blue thread guys'."
    )


_CANONICAL_TABLES: dict[CanonicalEntityType, tuple[str, str]] = {
    CanonicalEntityType.SUPPLIER: ("suppliers", "reference_code"),
    CanonicalEntityType.CUSTOMER: ("customers", "reference_code"),
    CanonicalEntityType.PURCHASE_ORDER: ("purchase_orders", "reference_code"),
    CanonicalEntityType.ORDER: ("orders", "reference_code"),
    CanonicalEntityType.INVENTORY_ITEM: ("inventory", "sku"),
}


def _reference_code_for(tenant_id: str, canonical_type: CanonicalEntityType, canonical_id: UUID) -> str | None:
    """Reverses `_lookup_canonical_id`: turns a knowledge_base row's
    internal canonical_id back into the human-facing code every other
    tool actually expects. Without this, `resolve_entity` would hand the
    model a raw UUID -- exactly the internal-only value the rest of the
    domain layer promises never to surface (see PLAN.md section 2).
    """
    table = _CANONICAL_TABLES.get(canonical_type)
    if table is None:
        return None
    table_name, code_column = table
    rows = run_query(
        f"SELECT {code_column} AS code FROM {table_name} WHERE tenant_id = %s AND id = %s",
        (tenant_id, canonical_id),
    )
    return rows[0]["code"] if rows else None


def _find_trusted_fuzzy(tenant_id: str, mention: str):
    """Step 1's fuzzy half: forgive minor phrasing noise against an
    already-trusted alias_text (never against a raw ERP name -- that's
    step 2's job and is never trusted silently).
    """
    best = None
    best_score = 0.0
    for entry in _knowledge_repo.list_trusted(tenant_id):
        score = _similarity(mention, entry.alias_text)
        if score > best_score:
            best, best_score = entry, score
    if best is not None and best_score >= _TRUSTED_FUZZY_THRESHOLD:
        return best
    return None


def _resolve_entity(args: ResolveEntityArgs, state: SessionState) -> str:
    trusted = _knowledge_repo.find_trusted(state.tenant_id, args.mention) or _find_trusted_fuzzy(
        state.tenant_id, args.mention
    )
    if trusted is not None:
        reference_code = _reference_code_for(state.tenant_id, trusted.canonical_type, trusted.canonical_id)
        pointer = reference_code or str(trusted.canonical_id)
        return (
            f"RESOLVED (trusted, source={trusted.source.value}): '{args.mention}' = "
            f"{trusted.canonical_type.value}:{pointer}. Use '{pointer}' as the search/reference "
            "value in other tools -- never the raw internal id."
        )

    candidates = _candidates_for_tenant(state.tenant_id, args.mention)[:_MAX_CANDIDATES_SHOWN]
    if not candidates:
        return f"UNRESOLVED: no candidates found for '{args.mention}'."

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = top["confidence"] - (second["confidence"] if second else 0.0)

    if top["confidence"] < _RESOLVED_THRESHOLD:
        status = "unresolved"
    elif second is not None and margin < _MARGIN_THRESHOLD:
        status = "ambiguous"
    else:
        status = "resolved"

    # Deliberately never prints the bare word "RESOLVED" here -- that word is
    # reserved for the trusted-lookup branch above. This is only a
    # classification of *candidate quality*, not a trust decision.
    lines = [
        f"CANDIDATES (classification={status}, none confirmed by a person -- do NOT treat any as fact):"
    ]
    for c in candidates:
        lines.append(
            f"- {c['canonical_type'].value}:{c['reference_code']} \"{c['label']}\" "
            f"(confidence={c['confidence']:.2f})"
        )
    lines.append(
        "If this mention matters for a number or fact in your answer, call ask_clarification with "
        "these candidates before using any of them -- even the top-scored one. Once the user picks "
        "one, call confirm_entity_link to record it; resolve_entity will then return it as trusted."
    )
    return "\n".join(lines)


resolve_entity_tool = Tool(
    name="resolve_entity",
    description=(
        "Look up what ERP record an informal mention refers to (e.g. 'supp B', '4812', 'the blue "
        "thread guys'). Checks the trusted knowledge base first; if nothing trusted matches, returns "
        "fuzzy candidates that must go through ask_clarification + confirm_entity_link before being "
        "trusted. Available to both the orchestrator and the retrieval sub-agent."
    ),
    args_schema=ResolveEntityArgs,
    handler=_resolve_entity,
)


def _lookup_canonical_id(tenant_id: str, canonical_type: CanonicalEntityType, reference_code: str) -> UUID | None:
    if canonical_type == CanonicalEntityType.SUPPLIER:
        entity = _supplier_repo.find_one_by_search_term(tenant_id, reference_code)
    elif canonical_type == CanonicalEntityType.CUSTOMER:
        entity = _customer_repo.find_one_by_search_term(tenant_id, reference_code)
    elif canonical_type == CanonicalEntityType.INVENTORY_ITEM:
        entity = _inventory_repo.find_one_by_search_term(tenant_id, reference_code)
    elif canonical_type == CanonicalEntityType.PURCHASE_ORDER:
        entity = _purchase_order_repo.get_by_reference_code(tenant_id, reference_code)
    else:
        entity = None
    return entity.id if entity else None


class ConfirmEntityLinkArgs(BaseModel):
    mention: str = Field(description="The exact informal phrase being confirmed, e.g. 'the blue thread guys'.")
    canonical_type: CanonicalEntityType = Field(description="Which kind of ERP record this mention refers to.")
    reference_code: str = Field(
        description="The human-facing reference_code of the exact record the user confirmed, e.g. 'SUP-1043'."
    )


def _confirm_entity_link(args: ConfirmEntityLinkArgs, state: SessionState) -> str:
    """Called only after a user has explicitly answered an
    `ask_clarification` question -- never on the strength of a model's
    own confidence, no matter how high `resolve_entity` scored it.
    """
    canonical_id = _lookup_canonical_id(state.tenant_id, args.canonical_type, args.reference_code)
    if canonical_id is None:
        return f"No {args.canonical_type.value} found with reference_code '{args.reference_code}'."

    entry = _knowledge_repo.insert_user_confirmed(
        state.tenant_id, args.mention, args.canonical_type, canonical_id
    )
    return (
        f"Recorded: '{entry.alias_text}' now resolves to {entry.canonical_type.value}:{args.reference_code} "
        "(source=user_confirmed). Future mentions of this phrase resolve directly, no more confirmation needed."
    )


confirm_entity_link_tool = Tool(
    name="confirm_entity_link",
    description=(
        "Record a user-confirmed mapping from an informal mention to an exact ERP record, after the "
        "user replies to an ask_clarification question. Never call this without an explicit user "
        "confirmation -- a high resolve_entity confidence score is not a confirmation."
    ),
    args_schema=ConfirmEntityLinkArgs,
    handler=_confirm_entity_link,
)

ENTITY_LINK_TOOLS = [resolve_entity_tool, confirm_entity_link_tool]
