"""The query-planning gate (Level 2.2): forces the orchestrator to decide
which source(s) a question needs -- SQL, chat, or both -- as an explicit,
structural step, instead of just wandering into whichever tool looks
convenient turn by turn.

Every SQL tool and `retrieve_from_chat` declare `REQUIRES_PLAN = True` and a
`SOURCE_KIND` (see app/tools/base.py); their `validate()` blocks them until
this tool has run, and further blocks them if the recorded plan says that
source isn't needed. That's what makes this a binding router, not a
checkbox: a model can't declare "sql only" and then use retrieve_from_chat
anyway. Calling plan_query again mid-turn overwrites the plan, so changing
your mind about what's needed is cheap.
"""

from pydantic import Field

from app.state.session_state import SessionState
from app.tools.base import ToolSchema


class PlanQueryTool(ToolSchema):
    TOOL_NAME = "plan_query"
    TOOL_DESCRIPTION = (
        "Required first step for any question that needs data: state what evidence you need, "
        "whether it requires SQL, chat retrieval, or both, and in what order (or note if the "
        "sources are independent). Every SQL tool and retrieve_from_chat are blocked until this "
        "runs, and are only unlocked according to what you declare here -- call it again if your "
        "needs change mid-turn."
    )

    needs_sql: bool = Field(
        description="Whether this question needs a number/status/date from the ERP."
    )
    needs_chat: bool = Field(
        description="Whether this question needs discussion/context from team chat."
    )
    reasoning: str = Field(
        description=(
            "1-2 sentences: what evidence is needed, from which source(s), and the order "
            "(or 'independent' if parallel)."
        )
    )

    def run(self, state: SessionState) -> str:
        state.query_plan = self.reasoning
        state.needs_sql = self.needs_sql
        state.needs_chat = self.needs_chat
        sql_status = "available" if self.needs_sql else "blocked for this plan"
        chat_status = "available" if self.needs_chat else "blocked for this plan"
        return (
            f"Plan recorded (sql={self.needs_sql}, chat={self.needs_chat}): {self.reasoning}. "
            f"SQL tools are {sql_status}; retrieve_from_chat is {chat_status}."
        )
