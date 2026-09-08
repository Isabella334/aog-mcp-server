"""AOG Smart Assistant MCP server.

Exposes four tools over the Model Context Protocol (stdio transport):

- get_aircraft_health: alert history + recurrence + criticality for a tail number.
- check_hangar_inventory: spare-part availability lookup, with alternatives.
- list_aircraft: every tracked tail number, with a quick 30-day health summary.
- list_inventory_parts: every hangar part, optionally filtered by status/model.

Data is served from bundled JSON files (data/aircraft_alerts.json,
data/inventory.json) that simulate a maintenance telemetry system and a
hangar inventory ERP. No real airline data or external systems are used.

This server is host-agnostic: it only depends on the `mcp` SDK and can be
run by any MCP client/host, not just the one it was developed against.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from aog_mcp_server.criticality import classify_criticality, is_recurring

DATA_DIR = Path(__file__).parent / "data"

mcp = FastMCP("aog-mcp-server")


def _load_json(filename: str) -> Any:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _today() -> date:
    return datetime.now().date()


_STOPWORDS = {"sensor", "unit", "system", "board", "circuit", "the", "of", "a"}


def _significant_words(name: str) -> set[str]:
    """Words in a part name that carry meaning for similarity matching,
    i.e. excluding generic hardware terms shared by unrelated parts."""
    words = {w.strip("()").lower() for w in name.split()}
    return {w for w in words if w and w not in _STOPWORDS}


@mcp.tool()
def get_aircraft_health(aircraft_id: str, days_lookback: int = 30) -> dict:
    """Look up an aircraft's recent alert history and assess recurrence/criticality.

    Queries the simulated telemetry alert log for the given tail number,
    keeps only alerts within the last `days_lookback` days, groups them by
    affected component, and flags a "recurring pattern" when the same
    component logs 2 or more alerts within that window. Criticality is
    derived from the alert code (see criticality.py) using an
    airworthiness-first scale: high / medium / low.

    Args:
        aircraft_id: Tail number, e.g. "HP-1234".
        days_lookback: How many days back to analyze (default 30).

    Returns:
        A dict with aircraft_id, alerts_found, recurring_pattern,
        affected_component, criticality, and the matching alert history.
    """
    aircraft_db = _load_json("aircraft_alerts.json")
    record = aircraft_db.get(aircraft_id)

    if record is None:
        return {
            "aircraft_id": aircraft_id,
            "error": f"No records found for aircraft '{aircraft_id}'.",
            "alerts_found": 0,
            "recurring_pattern": False,
            "affected_component": None,
            "criticality": None,
            "history": [],
        }

    cutoff = _today() - timedelta(days=days_lookback)
    recent_alerts = [
        alert
        for alert in record["alerts"]
        if datetime.strptime(alert["date"], "%Y-%m-%d").date() >= cutoff
    ]

    if not recent_alerts:
        return {
            "aircraft_id": aircraft_id,
            "model": record.get("model"),
            "alerts_found": 0,
            "recurring_pattern": False,
            "affected_component": None,
            "criticality": None,
            "history": [],
        }

    component_counts = Counter(alert["component"] for alert in recent_alerts)
    top_component, top_count = component_counts.most_common(1)[0]
    recurring = is_recurring(top_count)

    codes_for_top_component = [
        alert["code"] for alert in recent_alerts if alert["component"] == top_component
    ]
    criticality = classify_criticality(codes_for_top_component[0])

    return {
        "aircraft_id": aircraft_id,
        "model": record.get("model"),
        "alerts_found": len(recent_alerts),
        "recurring_pattern": recurring,
        "affected_component": top_component,
        "criticality": criticality,
        "history": recent_alerts,
    }


@mcp.tool()
def check_hangar_inventory(part_name: str, aircraft_model: str | None = None) -> dict:
    """Check hangar inventory for a spare part, returning stock and location.

    Looks for an exact (case-insensitive) name match first. If the part is
    out of stock or not found, searches for compatible alternatives for the
    given aircraft model.

    Args:
        part_name: Spare part name or code, e.g. "Oil pressure sensor ENG1".
        aircraft_model: Optional aircraft model to filter/find compatible
            alternatives, e.g. "Boeing 737-800".

    Returns:
        A dict with part_name, available, quantity, location, status, and
        a list of alternatives (each with the same shape) when applicable.
    """
    inventory = _load_json("inventory.json")
    normalized = part_name.strip().lower()

    match = next(
        (item for item in inventory if item["part_name"].strip().lower() == normalized),
        None,
    )

    if match and match["quantity"] > 0:
        return {
            "part_name": match["part_name"],
            "available": True,
            "quantity": match["quantity"],
            "location": match["location"],
            "status": match["status"],
            "alternatives": [],
        }

    alternatives = []
    if aircraft_model:
        requested_words = _significant_words(part_name)
        alternatives = [
            {
                "part_name": item["part_name"],
                "quantity": item["quantity"],
                "location": item["location"],
                "status": item["status"],
            }
            for item in inventory
            if item["quantity"] > 0
            and aircraft_model in item.get("compatible_models", [])
            and (match is None or item["part_name"] != match["part_name"])
            and requested_words & _significant_words(item["part_name"])
        ]

    if match is None:
        return {
            "part_name": part_name,
            "available": False,
            "quantity": 0,
            "location": None,
            "status": "not_found",
            "alternatives": alternatives,
        }

    return {
        "part_name": match["part_name"],
        "available": False,
        "quantity": match["quantity"],
        "location": match["location"],
        "status": match["status"],
        "alternatives": alternatives,
    }


@mcp.tool()
def list_aircraft() -> dict:
    """List every aircraft tail number tracked by this server.

    Includes each aircraft's model and a quick 30-day health summary
    (alerts found, criticality, recurring-pattern flag), so a host can
    show a fleet overview without querying each tail number individually.

    Returns:
        A dict with `count` and `aircraft` (a list of summaries).
    """
    aircraft_db = _load_json("aircraft_alerts.json")
    fleet = []
    for tail, record in aircraft_db.items():
        health = get_aircraft_health(tail)
        fleet.append(
            {
                "aircraft_id": tail,
                "model": record.get("model"),
                "alerts_last_30_days": health["alerts_found"],
                "criticality": health["criticality"],
                "recurring_pattern": health["recurring_pattern"],
            }
        )
    return {"count": len(fleet), "aircraft": fleet}


@mcp.tool()
def list_inventory_parts(status: str | None = None, aircraft_model: str | None = None) -> dict:
    """List hangar inventory parts, optionally filtered.

    Args:
        status: Optional filter - "available", "out_of_stock", or "in_transit".
        aircraft_model: Optional filter - only parts compatible with this model.

    Returns:
        A dict with `count` and `parts` (the matching inventory items).
    """
    inventory = _load_json("inventory.json")
    filtered = inventory
    if status:
        filtered = [p for p in filtered if p["status"] == status]
    if aircraft_model:
        filtered = [p for p in filtered if aircraft_model in p.get("compatible_models", [])]
    return {"count": len(filtered), "parts": filtered}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
