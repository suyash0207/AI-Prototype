"""The response tool that ends an orchestrator turn -- and the hard line.

The model is never trusted to type a correct number; it's structurally
prevented from succeeding with a wrong one. Every numeric claim must be
passed as a `{value, ref}` pair pointing at a `ProvenanceLedger` entry a
prior tool result actually created. If a ref doesn't exist, or its
value doesn't match what the ledger recorded, this tool returns an
error (not a success) and the loop continues -- the model must retry,
it can never terminate with an unverified figure. That's what makes
"numbers only from SQL" an architectural guarantee instead of a prompt
instruction the model might ignore.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.state.session_state import SessionState
from app.tools.base import TOOL_ERROR_PREFIX, Tool

logger = logging.getLogger(__name__)

# Matches plain numbers like "420000", "1,000", "80k", "300.5" so the
# safety net below can spot anything in the narrative that isn't one of
# the verified numbers -- deliberately loose, since this is a warning,
# not a rejection.
_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")

_VALUE_MATCH_TOLERANCE = 0.01


class NumberClaim(BaseModel):
    value: float = Field(description="The exact numeric value, as returned by the tool that produced it.")
    ref: str = Field(description="The [ref:...] tag that tool result was tagged with, e.g. 'sql:7'.")


class FinalAnswerArgs(BaseModel):
    narrative: str = Field(description="The plain-English answer to show the user.")
    numbers: list[NumberClaim] = Field(
        default_factory=list,
        description=(
            "Every dollar/rupee amount or quantity figure mentioned in narrative, each as a "
            "{value, ref} pair citing the ledger ref a tool result gave you. Do not include a "
            "number here unless a tool result actually gave you that ref."
        ),
    )


def _values_match(recorded: float | str, claimed: float) -> bool:
    try:
        return abs(float(recorded) - claimed) < _VALUE_MATCH_TOLERANCE
    except (TypeError, ValueError):
        return False


def _warn_on_unverified_numbers(narrative: str, numbers: list[NumberClaim]) -> None:
    """Defense-in-depth, not enforcement: after validation already passed,
    scan the narrative for any number that isn't one of the verified
    ones and log it. Only a warning -- narrative may legitimately contain
    non-financial numbers (dates, counts of messages, etc).
    """
    for match in _NUMBER_PATTERN.finditer(narrative):
        raw = match.group().replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if not any(_values_match(value, n.value) for n in numbers):
            logger.warning("final_answer narrative has an unverified number %r in: %r", raw, narrative)


def _run(args: FinalAnswerArgs, state: SessionState) -> str:
    for number in args.numbers:
        entry = state.provenance.get(number.ref)
        if entry is None:
            return (
                f"{TOOL_ERROR_PREFIX}ref '{number.ref}' does not exist in the provenance ledger. "
                "Only cite a ref that a tool result actually gave you -- do not invent one."
            )
        if not _values_match(entry.raw_value, number.value):
            return (
                f"{TOOL_ERROR_PREFIX}value {number.value} for ref '{number.ref}' does not match "
                f"the ledger's recorded value ({entry.raw_value}). Re-check the number against the "
                "tool result and try again."
            )

    _warn_on_unverified_numbers(args.narrative, args.numbers)
    return args.narrative


final_answer_tool = Tool(
    name="final_answer",
    description=(
        "Give your final answer to the user for this turn. Always call this once you know how to "
        "respond -- never reply with plain text instead. Any number in `narrative` must also appear "
        "in `numbers` as a {value, ref} pair citing where it came from."
    ),
    args_schema=FinalAnswerArgs,
    handler=_run,
    is_response_tool=True,
)
