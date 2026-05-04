"""
Norway Weather Demo - Bronze Ingestion Script
Calls Open-Meteo APIs for 8 Norwegian cities and writes raw JSON snapshots
to Bronze Delta tables via Databricks SQL statement execution.
Auth: reads profile 'dbx_free' from ~/.databrickscfg
Usage: .ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

PROFILE = "dbx_free"
CATALOG = "cop_weather_demo"
WEATHER_TABLE = f"{CATALOG}.bronze.openmeteo_weather_raw"
AIR_TABLE = f"{CATALOG}.bronze.openmeteo_air_raw"
WEATHER_BASE = "https://api.open-meteo.com/v1/forecast"
AIR_BASE = "https://air-quality-api.open-meteo.com/v1/air-quality"
CITIES_FILE = Path(__file__).parent.parent / "data" / "cities.json"


def http_get(base_url, params):
    qs = urllib.parse.urlencode(params)
    url = f"{base_url}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as response:
        body = response.read().decode("utf-8")
    return url, body


def insert_row(workspace_client, warehouse_id, table, run_ts, city, lat, lon, url, payload):
    url_esc = url.replace("'", "''")
    payload_esc = payload.replace("'", "''")
    stmt = (
        f"INSERT INTO {table} (run_ts,city,lat,lon,request_url,payload_json) "
        f"VALUES (TIMESTAMP '{run_ts}','{city}',{lat},{lon},'{url_esc}','{payload_esc}')"
    )
    result = workspace_client.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=stmt,
        wait_timeout="50s",
    )
    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"INSERT failed {city} -> {table}: {result.status.error}")


def main():
    print("Norway Weather Demo - Bronze Ingestion")
    cities = json.loads(CITIES_FILE.read_text())
    print(f"  Loaded {len(cities)} cities")
    workspace_client = WorkspaceClient(profile=PROFILE)
    warehouse = next(iter(workspace_client.warehouses.list()))
    print(f"  Warehouse: {warehouse.name} ({warehouse.id})")
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"  run_ts: {run_ts}\n")

    print("Ingesting weather forecast (sunshine_duration, 14 days)...")
    for city_info in cities:
        url, payload = http_get(
            WEATHER_BASE,
            {
                "latitude": city_info["lat"],
                "longitude": city_info["lon"],
                "daily": "sunshine_duration",
                "forecast_days": 14,
                "timezone": "Europe/Oslo",
            },
        )
        insert_row(
            workspace_client,
            warehouse.id,
            WEATHER_TABLE,
            run_ts,
            city_info["city"],
            city_info["lat"],
            city_info["lon"],
            url,
            payload,
        )
        print(f"  ✓ {city_info['city']}")

    print("\nIngesting air quality forecast (pm2_5 + european_aqi, 7 days)...")
    print("  [Note] Open-Meteo Air Quality API max forecast_days = 7")
    for city_info in cities:
        url, payload = http_get(
            AIR_BASE,
            {
                "latitude": city_info["lat"],
                "longitude": city_info["lon"],
                "hourly": "pm2_5,european_aqi",
                "forecast_days": 7,
                "timezone": "Europe/Oslo",
            },
        )
        insert_row(
            workspace_client,
            warehouse.id,
            AIR_TABLE,
            run_ts,
            city_info["city"],
            city_info["lat"],
            city_info["lon"],
            url,
            payload,
        )
        print(f"  ✓ {city_info['city']}")

    print(f"\nBronze ingestion complete. run_ts = {run_ts}")
    print(f"  {WEATHER_TABLE} -> 8 rows")
    print(f"  {AIR_TABLE}     -> 8 rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())