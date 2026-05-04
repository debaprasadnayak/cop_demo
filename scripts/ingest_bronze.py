"""
Norway Weather Demo – Bronze Ingestion Script
==============================================
Calls Open-Meteo APIs for 8 Norwegian cities and writes raw JSON snapshots
to Bronze Delta tables in Unity Catalog using the Databricks Python SDK.

Dependencies (all present in .ai-dev-kit/.venv):
  - databricks-sdk  (warehouse lookup + SQL statement execution)
  - urllib.request  (built-in, HTTP calls to Open-Meteo)

Usage:
  .ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py

Auth: reads profile 'dbx_free' from ~/.databrickscfg (or env vars from
      .databricks/.databricks.env via VS Code extension).
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

# ── Configuration ─────────────────────────────────────────────────────────────
PROFILE   = "dbx_free"
CATALOG   = "cop_weather_demo"
BRONZE    = "bronze"
WEATHER_TABLE = f"{CATALOG}.{BRONZE}.openmeteo_weather_raw"
AIR_TABLE     = f"{CATALOG}.{BRONZE}.openmeteo_air_raw"

WEATHER_BASE = "https://api.open-meteo.com/v1/forecast"
AIR_BASE     = "https://air-quality-api.open-meteo.com/v1/air-quality"

SCRIPT_DIR   = Path(__file__).parent
CITIES_FILE  = SCRIPT_DIR.parent / "data" / "cities.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def http_get(base_url: str, params: dict) -> tuple[str, str]:
    """Return (full_url, response_text). Raises on non-200."""
    qs  = urllib.parse.urlencode(params)
    url = f"{base_url}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        body = resp.read().decode("utf-8")
    return url, body


def sql_escape(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return s.replace("'", "''")


def insert_row(w: WorkspaceClient, warehouse_id: str,
               table: str, run_ts: str, city: str,
               lat: float, lon: float, url: str, payload: str) -> None:
    """INSERT one Bronze row synchronously via SQL statement execution."""
    url_esc     = sql_escape(url)
    payload_esc = sql_escape(payload)
    stmt = (
        f"INSERT INTO {table} (run_ts, city, lat, lon, request_url, payload_json) "
        f"VALUES ("
        f"  TIMESTAMP '{run_ts}', "
        f"  '{city}', "
        f"  {lat}, "
        f"  {lon}, "
        f"  '{url_esc}', "
        f"  '{payload_esc}'"
        f")"
    )
    result = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=stmt,
        wait_timeout="60s",
    )
    if result.status.state not in (StatementState.SUCCEEDED,):
        raise RuntimeError(
            f"INSERT failed for {city} into {table}: {result.status.error}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Norway Weather Demo – Bronze Ingestion")
    print(f"  Cities file : {CITIES_FILE}")
    print(f"  Catalog     : {CATALOG}")

    cities = json.loads(CITIES_FILE.read_text(encoding="utf-8"))
    print(f"  Loaded {len(cities)} cities")

    # Connect via SDK (reads profile dbx_free from ~/.databrickscfg or env)
    w = WorkspaceClient(profile=PROFILE)

    # Find best running warehouse
    warehouses = [wh for wh in w.warehouses.list() if wh.state and wh.state.value == "RUNNING"]
    if not warehouses:
        # Fall back to first available
        warehouses = list(w.warehouses.list())
    if not warehouses:
        print("ERROR: No SQL warehouses found. Create a warehouse in the Databricks UI.")
        return 1
    warehouse_id = warehouses[0].id
    print(f"  Warehouse   : {warehouses[0].name} ({warehouse_id})")

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"  run_ts      : {run_ts}\n")

    # ── Weather: sunshine_duration, 14-day forecast ──────────────────────────
    print("Ingesting weather forecast (sunshine_duration, 14 days)...")
    for c in cities:
        req_url, payload = http_get(WEATHER_BASE, {
            "latitude":      c["lat"],
            "longitude":     c["lon"],
            "daily":         "sunshine_duration",
            "forecast_days": 14,
            "timezone":      "Europe/Oslo",
        })
        insert_row(w, warehouse_id, WEATHER_TABLE,
                   run_ts, c["city"], c["lat"], c["lon"], req_url, payload)
        print(f"  ✓ {c['city']}")

    # ── Air Quality: pm2_5 + european_aqi, 7-day forecast (API max) ──────────
    print("\nIngesting air quality forecast (pm2_5 + european_aqi, 7 days)...")
    print("  [Note] Open-Meteo Air Quality API max forecast_days = 7")
    for c in cities:
        req_url, payload = http_get(AIR_BASE, {
            "latitude":      c["lat"],
            "longitude":     c["lon"],
            "hourly":        "pm2_5,european_aqi",
            "forecast_days": 7,
            "timezone":      "Europe/Oslo",
        })
        insert_row(w, warehouse_id, AIR_TABLE,
                   run_ts, c["city"], c["lat"], c["lon"], req_url, payload)
        print(f"  ✓ {c['city']}")

    print(f"\nBronze ingestion complete.  run_ts = {run_ts}")
    print(f"  {WEATHER_TABLE}  →  8 rows")
    print(f"  {AIR_TABLE}      →  8 rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
