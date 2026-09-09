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
