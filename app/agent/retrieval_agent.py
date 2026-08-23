"""The retrieval sub-agent: its own tiny loop, own ephemeral `SessionState`,
invoked as a tool by the orchestrator (see `app/tools/retrieve_from_chat_tool.py`).

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

from app.agent import fsm
from app.state.session_state import SessionState
from app.tools.base import build_tool_registry
from app.tools.resolve_entity_tool import ResolveEntityTool
from app.tools.return_claims_tool import ReturnClaimsTool
from app.tools.search_messages_tool import SearchMessagesTool

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "retrieval_agent.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()

RETRIEVAL_TOOLS = build_tool_registry([SearchMessagesTool, ResolveEntityTool, ReturnClaimsTool])


def run_retrieval(session_id: str, tenant_id: str, query: str) -> str:
    """Runs one full ephemeral retrieval loop, returns `return_claims`'
    raw JSON content (a `{"claims": [...]}` object as text).
    """
    state = SessionState(session_id, tenant_id, _SYSTEM_PROMPT)
    state.add_human_message(query)
    return fsm.run_workflow(state, RETRIEVAL_TOOLS)
