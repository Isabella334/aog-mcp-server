"""Criticality classification for aircraft alert codes.

Design convention (airworthiness-first, semaphore-style):
- "alta"  (high):   affects flight-critical systems (engine, hydraulics,
                     flight controls) -> airworthiness impact.
- "media" (medium):  affects secondary/avionics systems -> operational
                     impact but not immediately airworthiness-critical.
- "baja"  (low):    cabin comfort / cosmetic systems -> no airworthiness
                     impact.
"""

from __future__ import annotations

CODE_PREFIX_CRITICALITY: dict[str, str] = {
    "ENG": "alta",
    "HYD": "alta",
    "AVIO": "media",
    "CAB": "baja",
}

DEFAULT_CRITICALITY = "media"

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
