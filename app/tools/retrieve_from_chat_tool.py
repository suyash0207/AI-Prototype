"""Orchestrator-facing tool that runs the retrieval sub-agent's entire
loop under the hood and registers each returned claim into the
orchestrator's own `ProvenanceLedger` -- so `final_answer` can trace a
chat-derived claim back to a real message the same way it traces a
SQL number back to a real row, via one shared ref-checking mechanism.
"""

from __future__ import annotations

import json
import uuid

from pydantic import Field

from app.agent.retrieval_agent import run_retrieval
from app.domain.entities import ChatClaim
from app.state.session_state import SessionState
from app.tools.base import ToolSchema


class RetrieveFromChatTool(ToolSchema):
    TOOL_NAME = "retrieve_from_chat"
    TOOL_DESCRIPTION = (
        "Search the team chat for relevant discussion about a topic and get back structured facts "
        "(not raw messages), each tagged with a provenance ref. Use this instead of trying to search "
        "chat yourself -- you have no direct chat search tool."
    )

    query: str = Field(description="What to look for in the team chat history, in plain English.")

    def run(self, state: SessionState) -> str:
        session_id = f"retrieval:{state.session_id}:{uuid.uuid4().hex[:8]}"
        try:
            raw = run_retrieval(session_id, state.tenant_id, self.query)
            claim_dicts = json.loads(raw)["claims"]
        except Exception:  # noqa: BLE001 - a sub-agent failure degrades to "no results", not a crash
            return f"Chat retrieval failed for '{self.query}'; try rephrasing the query."

        if not claim_dicts:
            return f"No relevant chat claims found for '{self.query}'."

        lines: list[str] = []
        for c in claim_dicts:
            claim = ChatClaim(
                message_ref=c["message_ref"],
                sender=c["sender"],
                timestamp=c["timestamp"],
                extracted_claim=c["extracted_claim"],
                linked_entity=c.get("linked_entity"),
            )
            ref = state.provenance.register("chat", claim.message_ref, claim.extracted_claim)
            lines.append(f"{claim.to_llm_readable_output()} [ref:{ref}]")
        return "\n".join(lines)
