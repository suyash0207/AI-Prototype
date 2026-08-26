"""Deterministic, hardcoded thresholds/limits this system relies on.
Centralized here so every tunable cutoff lives in one place, instead of
being scattered across each tool file that happens to need one.
"""

# resolve_entity: how many ranked candidates to show when nothing trusted
# matches. Candidates are ranked by confidence, but nothing here decides
# trust -- see TRUSTED_FUZZY_THRESHOLD below for the one number that
# actually gates a decision. This is just a display cap.
MAX_CANDIDATES_SHOWN = 5

# How close a mention has to be to an already-trusted alias_text (not a
# raw ERP name) to still count as resolve_entity's deterministic lookup
# rather than a fresh fuzzy guess. Forgives minor phrasing noise (a
# trailing "'s") without letting a genuinely different phrase borrow an
# existing alias's trust -- this is the only threshold left in the system
# that decides anything; every other candidate resolve_entity finds
# (character- and embedding-similarity ranked, see resolve_entity_tool.py)
# is always routed through ask_clarification/confirm_entity_link, never
# auto-trusted off a score. Picked by eye, not statistically calibrated --
# the seed data only has ~3 known aliases per tenant, nowhere near enough
# to tune against -- but spot-checked: 0.92 for genuine phrasing noise,
# 0.67-0.69 for a genuinely different phrase, comfortably below this bar.
TRUSTED_FUZZY_THRESHOLD = 0.80

# final_answer: float-equality tolerance for verifying a claimed number
# against the ledger's recorded value.
VALUE_MATCH_TOLERANCE = 0.01

# search_messages: how many results to return per search. No longer an
# LLM-controllable argument (see app/tools/search_messages_tool.py) --
# fixed because the flexibility was never actually exercised.
SEARCH_MESSAGES_TOP_K = 5
