"""The top-level agent: owns its tool registry and prompt, and drives
the shared workflow loop against whichever session it's handed.
"""

from __future__ import annotations

from pathlib import Path

from app.agent import fsm
from app.state.store import get_or_create_session
from app.tools.base import build_tool_registry
from app.tools.final_answer_tool import final_answer_tool

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()

ORCHESTRATOR_TOOLS = build_tool_registry([final_answer_tool])


def handle_message(session_id: str, tenant_id: str, message: str) -> str:
    state = get_or_create_session(session_id, tenant_id, _SYSTEM_PROMPT)
    state.add_human_message(message)
    return fsm.run_workflow(state, ORCHESTRATOR_TOOLS)
