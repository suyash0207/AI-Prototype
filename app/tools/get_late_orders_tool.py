"""List every order that is not delivered/cancelled and whose promised
date has already passed.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from app.repositories.order_repository import OrderRepository
from app.state.session_state import SessionState
from app.tools.base import ToolSchema

_order_repo = OrderRepository()


class GetLateOrdersTool(ToolSchema):
    TOOL_NAME = "get_late_orders"
    TOOL_DESCRIPTION = (
        "List every order that is not delivered/cancelled and whose promised date has "
        "already passed."
    )

    as_of_date: date | None = Field(
        default=None,
        description="Compare promised dates against this date. Defaults to today if omitted.",
    )

    def run(self, state: SessionState) -> str:
        as_of = self.as_of_date or date.today()
        orders = _order_repo.list_late(state.tenant_id, as_of)
        if not orders:
            return f"No late orders as of {as_of.isoformat()}."
        return "\n".join(order.to_llm_readable_output() for order in orders)
