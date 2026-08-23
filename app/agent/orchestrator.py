"""The top-level agent: owns its tool registry and prompt, and drives
the shared workflow loop against whichever session it's handed.
"""

from __future__ import annotations

from pathlib import Path

from app.agent import fsm
from app.state.store import get_or_create_session
from app.tools.ask_clarification_tool import ask_clarification_tool
from app.tools.base import build_tool_registry
from app.tools.entity_link_tools import ENTITY_LINK_TOOLS
from app.tools.final_answer_tool import final_answer_tool
from app.tools.retrieval_tool import retrieve_from_chat_tool
from app.tools.sql_tools import SQL_TOOLS

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()

# `search_messages` is deliberately NOT here -- only the retrieval sub-agent
# (app/agent/retrieval_agent.py) calls it directly. The orchestrator only
# ever sees chat data as `retrieve_from_chat`'s structured, ledger-backed
# claims, never raw message text it could misquote.
ORCHESTRATOR_TOOLS = build_tool_registry(
    [final_answer_tool, ask_clarification_tool, *SQL_TOOLS, retrieve_from_chat_tool, *ENTITY_LINK_TOOLS]
)


def handle_message(session_id: str, tenant_id: str, message: str) -> str:
    state = get_or_create_session(session_id, tenant_id, _SYSTEM_PROMPT)
    state.add_human_message(message)
    return fsm.run_workflow(state, ORCHESTRATOR_TOOLS)
