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
    words = {w.strip("()").lower() for w in name.split()}
    return {w for w in words if w and w not in _STOPWORDS}


@mcp.tool()
def get_aircraft_health(aircraft_id: str, days_lookback: int = 30) -> dict:
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
