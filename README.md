# AOG MCP Server

A Model Context Protocol (MCP) server for **AOG (Aircraft On Ground)** triage. It gives any MCP-compatible host (chatbot, IDE agent, etc.) four tools to query a simulated airline maintenance environment:

1. **`get_aircraft_health`** — recent alert history for a tail number, with recurrence detection and criticality classification.
2. **`check_hangar_inventory`** — spare-part availability, location, and compatible alternatives.
3. **`list_aircraft`** — every tracked tail number, with a quick 30-day health summary.
4. **`list_inventory_parts`** — every hangar part, optionally filtered by status or compatible aircraft model.

Criticality levels and part-status values are kept in English (`high`/`medium`/`low`, `available`/`out_of_stock`/`in_transit`) regardless of the conversation language, mirroring how aircraft maintenance manuals (AMM) and minimum equipment lists (MEL) stay in English industry-wide.

Built for CC3067 (Networks, Universidad del Valle de Guatemala), Project 1 — "Use of an existing protocol". This server is intentionally generic: it depends only on the official `mcp` Python SDK and stdio transport, so it can be launched by **any** MCP host without modification.

## Requirements

- Python >= 3.11
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

## Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/Isabella334/aog-mcp-server.git
cd aog-mcp-server
uv sync
```

If you don't use `uv`, a plain virtualenv works too:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e .
```

## Running standalone (for testing)

```bash
uv run aog-mcp-server
```

This starts the server on **stdio** and blocks waiting for an MCP client. You won't see output — that's expected; it's talking JSON-RPC over stdin/stdout.

To inspect it interactively, use the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run aog-mcp-server
```

## Connecting it to an MCP host

Any host that can spawn a local stdio MCP server can use this. Example generic config (as used by Claude Desktop and similar hosts):

```json
{
  "mcpServers": {
    "aog": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/aog-mcp-server", "aog-mcp-server"]
    }
  }
}
```

If you installed it into an active environment instead, you can point directly at the console script:

```json
{
  "mcpServers": {
    "aog": {
      "command": "aog-mcp-server"
    }
  }
}
```

## Tool specifications

### `get_aircraft_health`

Looks up the simulated telemetry alert log for a tail number, filters to the requested time window, groups alerts by affected component, flags a **recurring pattern** when the same component logs 2+ alerts in that window, and assigns a **criticality** level (`high` / `medium` / `low`) based on the alert code (see `src/aog_mcp_server/criticality.py` for the ruleset).

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `aircraft_id` | string | yes | Tail number, e.g. `"HP-1234"` |
| `days_lookback` | integer | no (default `30`) | Time window to analyze, in days |

**Output**

```json
{
  "aircraft_id": "HP-1234",
  "model": "Boeing 737-800",
  "alerts_found": 3,
  "recurring_pattern": true,
  "affected_component": "Engine 1 - Oil pressure sensor",
  "criticality": "high",
  "history": [
    {"date": "2026-08-20", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."},
    {"date": "2026-08-25", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."},
    {"date": "2026-09-02", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."}
  ]
}
```

If the tail number has no records, an `error` field is returned instead, with empty history.

The bundled dataset covers **30 tail numbers** across 10 aircraft models (Boeing 737-800, 737 MAX 8, 787-8; Airbus A319, A320, A320neo, A321, A321neo; Embraer E190, E195; ATR 72-600), with a mix of scenarios: recurring high/medium-criticality faults, single-occurrence alerts at every criticality level, aircraft with no alerts on record (healthy), and one aircraft (`HP-8877` / `HP-3355`) whose alert predates the default 30-day lookback window (pass a larger `days_lookback` to see it). A representative sample:

| Tail | Model | Notable for |
|---|---|---|
| `HP-1234` | Boeing 737-800 | Recurring, high criticality (engine) |
| `HP-7788` | Airbus A320neo | Recurring, medium criticality (avionics/TCAS) |
| `HP-8801` | Boeing 787-8 | Recurring, high criticality (fuel system) |
| `HP-6655` | Embraer E195 | No alerts on record (healthy aircraft) |
| `HP-4499` | Airbus A321 | Alert exists but falls outside the default 30-day window |
| `HP-2211` | Boeing 737 MAX 8 | Single high-criticality alert (engine fire detection), not recurring |
| `HP-2298` | Embraer E190 | Single low-criticality alert (in-flight entertainment) |
| `HP-7745` | Airbus A320 | Single medium-criticality alert (APU) |

The full list of 30 tails and every alert is in [`src/aog_mcp_server/data/aircraft_alerts.json`](src/aog_mcp_server/data/aircraft_alerts.json).

### `check_hangar_inventory`

Looks up a spare part by name (case-insensitive exact match). If it's out of stock or unknown, and an `aircraft_model` is given, searches for compatible alternatives with stock available.

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `part_name` | string | yes | Spare part name, e.g. `"Oil pressure sensor ENG1"` |
| `aircraft_model` | string | no | Aircraft model to filter compatible alternatives, e.g. `"Boeing 737-800"` |

**Output**

```json
{
  "part_name": "Oil pressure sensor ENG1",
  "available": true,
  "quantity": 2,
  "location": "Hangar 2, Shelf B-14",
  "status": "available",
  "alternatives": []
}
```

### `list_aircraft`

Lists every tail number tracked by this server, with model and a quick 30-day health summary — useful when the host (or user) doesn't know which tail numbers exist yet.

**Input:** none.

**Output**

```json
{
  "count": 30,
  "aircraft": [
    {"aircraft_id": "HP-1234", "model": "Boeing 737-800", "alerts_last_30_days": 3, "criticality": "high", "recurring_pattern": true},
    {"aircraft_id": "HP-5678", "model": "Airbus A320", "alerts_last_30_days": 0, "criticality": null, "recurring_pattern": false}
  ]
}
```

### `list_inventory_parts`

Lists hangar inventory parts, optionally filtered.

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | no | Filter by `"available"`, `"out_of_stock"`, or `"in_transit"` |
| `aircraft_model` | string | no | Filter to parts compatible with this model |

**Output**

```json
{
  "count": 5,
  "parts": [
    {"part_name": "Cabin temperature control unit", "compatible_models": ["Airbus A320"], "quantity": 0, "location": "Hangar 1, Shelf C-02", "status": "out_of_stock"}
  ]
}
```

## Data source

All four tools read from bundled JSON files that simulate a maintenance telemetry log and a hangar inventory system:

- `src/aog_mcp_server/data/aircraft_alerts.json`
- `src/aog_mcp_server/data/inventory.json`

No real airline data, telemetry feeds, or external systems are used — this is fictional data for the course project.

## Project context

This server is part of the **AOG Smart Assistant** project for CC3067 Redes (UVG). The chatbot/host that consumes it lives in a separate, private repository (`aog-smart-assistant`), per the assignment's requirement to publish the MCP server independently and publicly so classmates can integrate it into their own hosts.
