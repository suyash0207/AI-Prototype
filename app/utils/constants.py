"""Deterministic, hardcoded thresholds used to classify fuzzy-match/
numeric-verification results. Centralized here so every tunable cutoff
this system relies on lives in one place, instead of being scattered
across each tool file that happens to need one.
"""

# resolve_entity: fuzzy-match classification cutoffs.
# A "resolved" classification needs the top candidate at/above
# RESOLVED_THRESHOLD, AND a clear enough gap over the runner-up
# (MARGIN_THRESHOLD) -- both deterministic cutoffs, not model judgment.
# Tuned loose enough to catch typos/shorthand ("supp B", "4812") without
# being so loose it treats an unrelated name as a near-miss.
RESOLVED_THRESHOLD = 0.55
MARGIN_THRESHOLD = 0.15
MAX_CANDIDATES_SHOWN = 5

# How close a mention has to be to an already-trusted alias_text (not a
# raw ERP name) to still count as resolve_entity's deterministic lookup
# rather than a fresh fuzzy guess. Much stricter than RESOLVED_THRESHOLD --
# this only forgives minor phrasing noise ("the dye guys" vs "dye guys",
# a trailing "'s"), it never lets a genuinely different phrase borrow an
# existing alias's trust.
TRUSTED_FUZZY_THRESHOLD = 0.75

# final_answer: float-equality tolerance for verifying a claimed number
# against the ledger's recorded value.
VALUE_MATCH_TOLERANCE = 0.01

# search_messages: how many results to return per search. No longer an
# LLM-controllable argument (see app/tools/search_messages_tool.py) --
# fixed because the flexibility was never actually exercised.
SEARCH_MESSAGES_TOP_K = 5
