# AOG MCP Server

A Model Context Protocol (MCP) server for **AOG (Aircraft On Ground)** triage. It gives any MCP-compatible host (chatbot, IDE agent, etc.) two tools to query a simulated airline maintenance environment:

1. **`get_aircraft_health`** — recent alert history for a tail number, with recurrence detection and criticality classification.
2. **`check_hangar_inventory`** — spare-part availability, location, and compatible alternatives.

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

Looks up the simulated telemetry alert log for a tail number, filters to the requested time window, groups alerts by affected component, flags a **recurring pattern** when the same component logs 2+ alerts in that window, and assigns a **criticality** level (`alta` / `media` / `baja`) based on the alert code (see `src/aog_mcp_server/criticality.py` for the ruleset).

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
  "criticality": "alta",
  "history": [
    {"date": "2026-08-20", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."},
    {"date": "2026-08-25", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."},
    {"date": "2026-09-02", "code": "ENG1-OILP-04", "component": "Engine 1 - Oil pressure sensor", "description": "..."}
  ]
}
```

If the tail number has no records, an `error` field is returned instead, with empty history.

Sample tail numbers available in the bundled dataset: `HP-1234`, `HP-5678`, `HP-9012`, `HP-3344`.

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

## Data source

Both tools read from bundled JSON files that simulate a maintenance telemetry log and a hangar inventory system:

- `src/aog_mcp_server/data/aircraft_alerts.json`
- `src/aog_mcp_server/data/inventory.json`

No real airline data, telemetry feeds, or external systems are used — this is fictional data for the course project.

## Project context

This server is part of the **AOG Smart Assistant** project for CC3067 Redes (UVG). The chatbot/host that consumes it lives in a separate, private repository (`aog-smart-assistant`), per the assignment's requirement to publish the MCP server independently and publicly so classmates can integrate it into their own hosts.
