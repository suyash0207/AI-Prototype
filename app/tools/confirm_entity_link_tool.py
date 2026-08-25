"""Record a user-confirmed mapping from an informal mention to an exact
ERP record. Called only after a user has explicitly answered an
`ask_clarification` question -- never on the strength of a model's own
confidence, no matter how high `resolve_entity` scored it.
"""

from uuid import UUID

from pydantic import Field

from app.domain.enums import CanonicalEntityType
from app.repositories.customer_repository import CustomerRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.supplier_repository import SupplierRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_knowledge_repo = KnowledgeBaseRepository()
_supplier_repo = SupplierRepository()
_customer_repo = CustomerRepository()
_inventory_repo = InventoryRepository()
_purchase_order_repo = PurchaseOrderRepository()


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


class ConfirmEntityLinkTool(ToolSchema):
    TOOL_NAME = "confirm_entity_link"
    TOOL_DESCRIPTION = (
        "Record a user-confirmed mapping from an informal mention to an exact ERP record, after the "
        "user replies to an ask_clarification question. Never call this without an explicit user "
        "confirmation -- a high resolve_entity confidence score is not a confirmation."
    )

    mention: str = Field(description="The exact informal phrase being confirmed, e.g. 'the blue thread guys'.")
    canonical_type: CanonicalEntityType = Field(description="Which kind of ERP record this mention refers to.")
    reference_code: str = Field(
        description="The human-facing reference_code of the exact record the user confirmed, e.g. 'SUP-1043'."
    )

    def run(self, state: SessionState) -> str:
        canonical_id = _lookup_canonical_id(state.tenant_id, self.canonical_type, self.reference_code)
        if canonical_id is None:
            return f"No {self.canonical_type.value} found with reference_code '{self.reference_code}'."

        entry = _knowledge_repo.insert_user_confirmed(
            state.tenant_id, self.mention, self.canonical_type, canonical_id
        )
        return (
            f"Recorded: '{entry.alias_text}' now resolves to {entry.canonical_type.value}:{self.reference_code} "
            "(source=user_confirmed). Future mentions of this phrase resolve directly, no more confirmation needed."
        )
