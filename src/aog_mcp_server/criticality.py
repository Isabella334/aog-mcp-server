"""Criticality classification for aircraft alert codes.

Levels are kept in English ("high"/"medium"/"low") rather than localized,
by the same convention that keeps aircraft maintenance manuals (AMM) and
minimum equipment lists (MEL) in English industry-wide regardless of the
reader's language - technical/system-level labels stay in English, while
the assistant's conversational responses are bilingual (see the host's
system prompt).

Design convention (airworthiness-first, semaphore-style):
- "high":   affects flight-critical systems (engine, hydraulics, flight
            controls, fuel, landing gear) -> airworthiness impact.
- "medium": affects secondary/avionics/electrical systems -> operational
            impact but not immediately airworthiness-critical.
- "low":    cabin comfort / cosmetic systems -> no airworthiness impact.
"""

from __future__ import annotations

CODE_PREFIX_CRITICALITY: dict[str, str] = {
    "ENG": "high",
    "HYD": "high",
    "FLT": "high",   # flight controls
    "FUEL": "high",
    "LDG": "high",   # landing gear
    "AVIO": "medium",
    "ELEC": "medium",
    "APU": "medium",
    "CAB": "low",
    "IFE": "low",   # in-flight entertainment
    "LAV": "low",
    "WIFI": "low",
}

DEFAULT_CRITICALITY = "medium"

RECURRENCE_THRESHOLD = 2


def classify_criticality(code: str) -> str:
    """Map an alert code (e.g. 'ENG1-OILP-04') to a criticality level."""
    prefix = code.split("-")[0]
    for known_prefix, level in CODE_PREFIX_CRITICALITY.items():
        if prefix.startswith(known_prefix):
            return level
    return DEFAULT_CRITICALITY


def is_recurring(occurrences: int) -> bool:
    return occurrences >= RECURRENCE_THRESHOLD
