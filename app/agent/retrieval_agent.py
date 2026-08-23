"""The retrieval sub-agent: its own tiny loop, own ephemeral `SessionState`,
invoked as a tool by the orchestrator (see `app/tools/retrieval_tool.py`).

Exists to keep "find and extract facts from chat" a separate,
structured-output-only responsibility. It can reformulate/re-search
internally via `search_messages` and link informal mentions via
`resolve_entity`, but it must terminate by handing back structured
facts (`return_claims`), never prose -- that's what lets the
orchestrator register each claim into its own `ProvenanceLedger` and
later cross-check it against SQL (Phase 4's contradiction detection),
instead of just trusting a paragraph of retrieval-agent-written text.

Its own conversation (internal tool calls, reformulations) is never
persisted anywhere -- a fresh `SessionState` is constructed per call
and discarded once this function returns.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.agent import fsm
from app.state.session_state import SessionState
from app.tools.base import Tool, build_tool_registry
from app.tools.entity_link_tools import resolve_entity_tool
from app.tools.search_tools import search_messages_tool

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "retrieval_agent.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()


class ChatClaimArg(BaseModel):
    message_ref: str          # which chat message this claim came from, e.g. "msg_002"
    sender: str                # who sent that message
    timestamp: str             # ISO timestamp of that message, taken verbatim from search_messages
    extracted_claim: str        # the plain-English fact pulled out of the message
    linked_entity: str | None = None  # resolved reference_code this claim is about, if resolve_entity found one


class ReturnClaimsArgs(BaseModel):
    claims: list[ChatClaimArg]  # every relevant fact found, or [] if nothing relevant turned up


def _return_claims(args: ReturnClaimsArgs, state: SessionState) -> str:
    return args.model_dump_json()


return_claims_tool = Tool(
    name="return_claims",
    description=(
        "Terminate with your findings as a structured list of claims -- never as prose. Call this "
        "even if you found nothing relevant, with an empty claims list."
    ),
    args_schema=ReturnClaimsArgs,
    handler=_return_claims,
    is_response_tool=True,
)

RETRIEVAL_TOOLS = build_tool_registry([search_messages_tool, resolve_entity_tool, return_claims_tool])


def run_retrieval(session_id: str, tenant_id: str, query: str) -> str:
    """Runs one full ephemeral retrieval loop, returns `return_claims`'
    raw JSON content (a `{"claims": [...]}` object as text).
    """
    state = SessionState(session_id, tenant_id, _SYSTEM_PROMPT)
    state.add_human_message(query)
    return fsm.run_workflow(state, RETRIEVAL_TOOLS)
