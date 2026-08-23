"""Registers where every number and chat claim actually came from.

Exists so `final_answer` can *prove* a figure traces back to a real
tool result instead of trusting the model not to invent one -- the
model never gets to state a number, only cite a ref this ledger
already holds. One instance per session, created in `SessionState`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceType = Literal["sql", "chat"]


@dataclass(frozen=True)
class ProvenanceEntry:
    ref: str                 # e.g. "sql:7" or "chat:3" -- what a tool result/final_answer cites
    source_type: SourceType  # sql = a structured DB query, chat = a retrieved message
    source_id: str           # human-readable pointer to where this came from, e.g. "invoices for CUST-0078" or "msg:tenant_a:msg_001"
    raw_value: float | str    # the exact value this ref vouches for


class ProvenanceLedger:
    """An append-only table of `{ref, source, value}` entries for one session.

    Every SQL/chat tool result that reaches the model gets registered
    here *before* the model sees it. `final_answer` then has to cite a
    ref from this ledger for every numeric claim -- if the ref doesn't
    exist, or its value doesn't match what's recorded, the answer is
    rejected. This is what makes "numbers only from SQL" an
    architectural fact rather than a prompted hope.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ProvenanceEntry] = {}
        self._next_id = 1

    def register(self, source_type: SourceType, source_id: str, raw_value: float | str) -> str:
        """Records one value and returns the ref the model should cite for it."""
        ref = f"{source_type}:{self._next_id}"
        self._next_id += 1
        self._entries[ref] = ProvenanceEntry(
            ref=ref, source_type=source_type, source_id=source_id, raw_value=raw_value
        )
        return ref

    def tag(self, source_type: SourceType, source_id: str, raw_value: float | str) -> str:
        """Register + format in one step -- returns text like "420000 [ref:sql:7]"
        for a SQL tool to splice directly into its result string.
        """
        ref = self.register(source_type, source_id, raw_value)
        return f"{raw_value} [ref:{ref}]"

    def get(self, ref: str) -> ProvenanceEntry | None:
        return self._entries.get(ref)
