"""Process-local session store.

A plain in-memory dict, nothing more. There is no TTL eviction and no
fallback to any persistent store on purpose: restarting the process
drops every session, by design.
"""

from __future__ import annotations

from app.state.session_state import SessionState

_sessions: dict[str, SessionState] = {}


def get_or_create_session(session_id: str, tenant_id: str, system_prompt: str) -> SessionState:
    session = _sessions.get(session_id)
    if session is None:
        session = SessionState(session_id, tenant_id, system_prompt)
        _sessions[session_id] = session
    return session


def clear_all_sessions() -> None:
    """Used by tests to reset state between runs without restarting the process."""
    _sessions.clear()
