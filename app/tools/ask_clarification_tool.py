"""The second response tool: ends the turn by asking the user to pick
between candidate entity links instead of answering.

Exists because entity linking must never silently guess when a mention
is material to a fact/number in the answer -- the explainer's own rule
that a wrong link must never silently corrupt a figure. Marked
`is_response_tool=True`, same termination path as `final_answer`: the
loop ends either way, but this one hands the candidate list back to
the user instead of a completed answer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.state.session_state import SessionState
from app.tools.base import Tool


class ClarificationCandidate(BaseModel):
    label: str = Field(description="Human-readable description, e.g. 'Supplier B Ltd. (SUP-1043)'.")
    canonical_type: str = Field(description="Which kind of ERP record this is, e.g. 'supplier'.")
    reference_code: str = Field(description="The candidate's human-facing reference_code, e.g. 'SUP-1043'.")


class AskClarificationArgs(BaseModel):
    question: str = Field(
        description='The question to show the user, e.g. "Did you mean Supplier B Ltd. (SUP-1043)?"'
    )
    candidates: list[ClarificationCandidate] = Field(description="The options the user can pick from.")


def _run(args: AskClarificationArgs, state: SessionState) -> str:
    lines = [args.question]
    for c in args.candidates:
        lines.append(f"- {c.label} ({c.canonical_type}:{c.reference_code})")
    return "\n".join(lines)


ask_clarification_tool = Tool(
    name="ask_clarification",
    description=(
        "End this turn by asking the user to confirm which real-world record an ambiguous mention "
        "refers to, instead of answering outright. Use whenever an unresolved/ambiguous entity link "
        "(from resolve_entity) is material to the answer -- especially anything feeding a number. "
        "Once the user replies, call confirm_entity_link with their choice."
    ),
    args_schema=AskClarificationArgs,
    handler=_run,
    is_response_tool=True,
)
