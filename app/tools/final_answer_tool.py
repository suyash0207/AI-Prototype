"""The response tool that ends an orchestrator turn.

This is deliberately bare for now: it just hands back whatever text the
model wrote. Nothing about the answer is checked here yet — that
validation (numbers/claims must trace back to a prior tool result) gets
added once there are tools whose results actually need tracing back to.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.state.session_state import SessionState
from app.tools.base import Tool


class FinalAnswerArgs(BaseModel):
    answer: str


def _run(args: FinalAnswerArgs, state: SessionState) -> str:
    return args.answer


final_answer_tool = Tool(
    name="final_answer",
    description=(
        "Give your final answer to the user for this turn. Always call this "
        "once you know how to respond — never reply with plain text instead."
    ),
    args_schema=FinalAnswerArgs,
    handler=_run,
    is_response_tool=True,
)
