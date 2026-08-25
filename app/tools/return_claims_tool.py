"""The retrieval sub-agent's own response tool: terminates its loop with
a structured list of claims, never prose -- that's what lets the
orchestrator register each claim into its own `ProvenanceLedger` and
later cross-check it against SQL, instead of just trusting a paragraph
of retrieval-agent-written text.
"""

from pydantic import BaseModel

from app.state.session_state import SessionState
from app.tools.base import ToolSchema


class ChatClaimArg(BaseModel):
    message_ref: str          # which chat message this claim came from, e.g. "msg_002"
    sender: str                # who sent that message
    timestamp: str             # ISO timestamp of that message, taken verbatim from search_messages
    extracted_claim: str        # the plain-English fact pulled out of the message
    linked_entity: str | None = None  # resolved reference_code this claim is about, if resolve_entity found one


class ReturnClaimsTool(ToolSchema):
    TOOL_NAME = "return_claims"
    TOOL_DESCRIPTION = (
        "Terminate with your findings as a structured list of claims -- never as prose. Call this "
        "even if you found nothing relevant, with an empty claims list."
    )
    IS_RESPONSE_TOOL = True

    claims: list[ChatClaimArg]  # every relevant fact found, or [] if nothing relevant turned up

    def run(self, state: SessionState) -> str:
        return self.model_dump_json()
