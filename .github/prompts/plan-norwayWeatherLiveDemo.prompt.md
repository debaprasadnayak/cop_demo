---
mode: agent
description: >
  Norway Weather Live Demo – Zero-to-live build for Databricks.
  Starting from an empty cop_demo/ folder, this prompt orchestrates two
  specialist agents to create every file, catalog object, pipeline, dashboard
  and Genie Space live during the demo session.
  Agent A (Senior Data Engineer – Databricks): creates all source files,
  deploys the Databricks Asset Bundle, provisions UC objects, ingests Bronze
  data, and runs the SDP pipeline.
  Agent B (Analytics Reporter): creates the AI/BI Dashboard and
  Genie Space from Gold tables.
  At each GO/NO-GO gate the agent pauses and waits for presenter approval
  before continuing.
  Every agent must log its start time, completion time, and output file path.
  ONLY USE THE DATABRICKS SERVERLESS, DO NOT CREATE ANY CLUSTER
  UPDATE the `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`
  file immediately if any bug or issues encountered during the run, and that
  can be patched in the prompt so the next run is smooth. The checklist file is
  the source of truth for the demo status.
---

# Norway Weather Demo – Agent Mode Build Prompt

> **Starting state**: The `cop_demo/` folder contains only `README.md` and
> `LICENSE`. The `databricks.yml` bundle config exists but has no pipeline
> includes. Nothing else pre-exists.
>
> **How to run**: Select the **Agents Orchestrator** agent in GitHub Copilot
> Chat, open this file, and click **"Run Prompt"**. The orchestrator delegates
> to the two specialist agents below and uses Databricks MCP tools + terminal
> commands throughout. At each **[GO/NO-GO GATE]** the agent surfaces results
> and waits for you to type **GO** (continue) or **NO** (troubleshoot).
>
> **Re-run safety**: Bronze tables are append-only. Each run creates a new
> `run_ts` snapshot. Silver/Gold are rebuilt from the latest `run_ts` by the
> pipeline. Run the cleanup block at the end to reset completely.

## Execution Checklist Artifact (Mandatory)

Before Phase A starts, create this file:

`cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`

This file is a live status tracker and MUST be updated immediately after each
step/gate is implemented.

- Allowed status values only: `Done`, `Pending`, `Failed`
- Default all items to `Pending`
- On success set to `Done`
- On error/blocker set to `Failed` and add a one-line reason under the item
 
Use this template:

```md
# Norway Weather Live Demo - High-Level Checklist

Run Start Time: {ISO-8601}
Run End Time: {ISO-8601 or N/A}

## Phase A - Senior Data Engineer
- [ ] A0 Auth pre-flight - Status: Pending
- [ ] A1 Create source files - Status: Pending
- [ ] A2 UC catalog/schemas/tables - Status: Pending
- [ ] A3 Bundle validate + deploy - Status: Pending
- [ ] Gate 1 Catalog + tables ready - Status: Pending
- [ ] A4 Bronze ingestion - Status: Pending
- [ ] Gate 2 Bronze populated - Status: Pending
- [ ] A5 SDP pipeline run - Status: Pending
- [ ] Gate 3 Gold populated - Status: Pending

## Phase B - Analytics Reporter
- [ ] B1 Dashboard build + publish - Status: Pending
- [ ] Gate 4 Dashboard live - Status: Pending
- [ ] B2 Genie space + smoke tests - Status: Pending
- [ ] Gate 5 Genie live - Status: Pending
- [ ] B3 Live Q&A finale - Status: Pending

## Notes
- {timestamp} {short note}
```

At the end of the run, set `Run End Time` and ensure no executed step remains `Pending`.

---

## Agent Roles

| Agent | Responsibility |
|-------|----------------|
| **Senior Data Engineer – Databricks** | Phase A: create all repo files, update bundle, provision UC objects, ingest Bronze, run SDP pipeline |
| **Analytics Reporter** | Phase B: create AI/BI Dashboard + Genie Space, run live Q&A smoke-test |

The **Agents Orchestrator** (this prompt's runner) sequences the two phases and
enforces the GO/NO-GO gates between them.

---

## Demo Data Model

| Layer | Table | Rows/run | Key columns |
|-------|-------|----------|-------------|
| Bronze | `openmeteo_weather_raw` | 8 | run_ts, city, payload_json |
| Bronze | `openmeteo_air_raw` | 8 | run_ts, city, payload_json |
| Bronze | `ref_cities` | 8 (static) | city, lat, lon |
| Silver | `weather_daily` | 112 (8×14 days) | run_ts, city, date, sunshine_duration_seconds |
| Silver | `air_hourly` | ~1 344 (8×168 h) | run_ts, city, ts, pm2_5, european_aqi |
| Gold | `sunshine_14d_rank` | 8 | run_ts, city, sunshine_hours_14d, rank |
| Gold | `clean_air_rank` | 8 | run_ts, city, avg_pm2_5_horizon, avg_european_aqi_horizon, rank_pm25, rank_aqi |

### API Horizon Constraint (documented)

| Metric | Endpoint | `forecast_days` | Horizon |
|--------|----------|-----------------|---------|
| `sunshine_duration` | `api.open-meteo.com/v1/forecast` | 14 | **14 days** |
| `pm2_5`, `european_aqi` | `air-quality-api.open-meteo.com/v1/air-quality` | 7 | **7 days** (API max) |

> Demo Q1 = "next **14** days". Demo Q2 = "next **7** days". Both phrasings are honest.
> Open-Meteo Air Quality API `forecast_days` parameter maximum = 7 (CAMS European 4-day
> + CAMS Global 5-day blend). No workaround needed — 7 days is sufficient for ranking.

---

## Metric Definitions (reference for both agents)

**Sunniest city**
- `sunshine_hours_14d = SUM(daily.sunshine_duration_seconds) / 3600.0`
- Ranked DESCENDING — `rank = 1` is the sunniest.

**Cleanest air city**
- Primary: `avg_pm2_5_horizon = AVG(hourly.pm2_5)` over 7-day horizon → `rank_pm25` ASC (1 = cleanest)
- Secondary: `avg_european_aqi_horizon = AVG(hourly.european_aqi)` → `rank_aqi` ASC (1 = cleanest)
- The two ranks are INDEPENDENT.

---

## ════════════════════════════════════════════════════════
## PHASE A  ·  Senior Data Engineer – Databricks
## ════════════════════════════════════════════════════════

> Invoke the **Senior Data Engineer – Databricks** agent for all steps in
> Phase A. This agent uses the `databricks-spark-declarative-pipelines` skill,
> Databricks MCP tools, and terminal commands.

### Phase A Runtime Guardrails (Mandatory)

Use these exact constants for every Phase A shell execution:

- `WORKSPACE_ROOT=/Users/debanayak/Library/CloudStorage/OneDrive-Capgemini/Code Workspace/databricks codespace`
- `VENV_PY=/Users/debanayak/.ai-dev-kit/.venv/bin/python`

Rules:

1. Always `cd "$WORKSPACE_ROOT"` before running bundle or ingestion commands.
2. For Bronze ingestion, use ONLY `$VENV_PY` and never `python`, `python3`, `uv run`, or any fallback interpreter.
3. Before ingestion, run this interpreter preflight and proceed only if it passes:

```bash
cd "$WORKSPACE_ROOT"
test -x "$VENV_PY"
"$VENV_PY" -c "import sys; print(sys.executable)"
```

Expected stdout must be exactly:

`/Users/debanayak/.ai-dev-kit/.venv/bin/python`

### Databricks Tooling Policy (Mandatory)

Use the appropriate Databricks MCP tool first for every Databricks control-plane/data-plane action.
Use Databricks CLI only as failover if MCP returns an error, timeout, or unavailable capability.

Failover rules:

1. Try MCP first once.
2. If MCP fails, record the exact MCP error text in checklist notes.
3. Run the CLI fallback command once.
4. If fallback also fails, stop and mark the step `Failed`.

MCP-first mapping for this prompt:

- UC SQL DDL/DML/validation queries: `mcp_databricks_execute_sql` / `mcp_databricks_execute_sql_multi`
- SDP pipeline run/status/events: `mcp_databricks_manage_pipeline_run`
- Dashboard create/publish: `mcp_databricks_manage_dashboard`
- Genie create/query: `mcp_databricks_manage_genie`, `mcp_databricks_ask_genie`

CLI exception:

- Databricks Asset Bundle validate/deploy (`databricks bundle ...`) has no direct MCP equivalent in this workspace; CLI is allowed as primary for A3.

---

## A1 — Create All Source Files

After A1 is implemented, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A1 Create source files` to `Done` or `Failed`

The agent creates every file from scratch. The `cop_demo/` folder is currently
empty (only `README.md` and `LICENSE`). The agent must create the following
files with the exact content specified below.

### A1.1 — Create `cop_demo/data/cities.json`

Hardcoded Norwegian city coordinates. No geocoding API call — ever.

```json
[
  {"city": "Bergen",       "lat": 60.3913, "lon":  5.3221},
  {"city": "Oslo",         "lat": 59.9139, "lon": 10.7522},
  {"city": "Trondheim",    "lat": 63.4305, "lon": 10.3951},
  {"city": "Stavanger",    "lat": 58.9700, "lon":  5.7331},
  {"city": "Tromsø",       "lat": 69.6492, "lon": 18.9553},
  {"city": "Kristiansand", "lat": 58.1599, "lon":  8.0182},
  {"city": "Ålesund",      "lat": 62.4722, "lon":  6.1495},
  {"city": "Bodø",         "lat": 67.2804, "lon": 14.4049}
]
```

### A1.2 — Create `cop_demo/scripts/ingest_bronze.py`

Standalone Python script. Uses only `databricks-sdk` (present in
`.ai-dev-kit/.venv`) and built-in `urllib.request`. No extra installs.

```python
"""
Norway Weather Demo – Bronze Ingestion Script
Calls Open-Meteo APIs for 8 Norwegian cities and writes raw JSON snapshots
to Bronze Delta tables via Databricks SQL statement execution.
Auth: reads profile from ~/.databrickscfg (configure below)
Usage: /Users/debanayak/.ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py
"""
import json, sys, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

PROFILE       = "YOUR_PROFILE"
WAREHOUSE_ID  = "YOUR_WAREHOUSE_ID"
CATALOG       = "cop_weather_demo"
WEATHER_TABLE = f"{CATALOG}.bronze.openmeteo_weather_raw"
AIR_TABLE     = f"{CATALOG}.bronze.openmeteo_air_raw"
WEATHER_BASE  = "https://api.open-meteo.com/v1/forecast"
AIR_BASE      = "https://air-quality-api.open-meteo.com/v1/air-quality"
CITIES_FILE   = Path(__file__).parent.parent / "data" / "cities.json"

def http_get(base_url, params):
    qs  = urllib.parse.urlencode(params)
    url = f"{base_url}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as r:
        body = r.read().decode("utf-8")
    return url, body

def insert_row(w, wh_id, table, run_ts, city, lat, lon, url, payload):
    url_esc     = url.replace("'", "''")
    payload_esc = payload.replace("'", "''")
    stmt = (
        f"INSERT INTO {table} (run_ts,city,lat,lon,request_url,payload_json) "
        f"VALUES (TIMESTAMP '{run_ts}','{city}',{lat},{lon},'{url_esc}','{payload_esc}')"
    )
    res = w.statement_execution.execute_statement(
        warehouse_id=wh_id, statement=stmt, wait_timeout="50s"
    )
    if res.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"INSERT failed {city} → {table}: {res.status.error}")

def main():
    print("Norway Weather Demo – Bronze Ingestion")
    cities = json.loads(CITIES_FILE.read_text())
    print(f"  Loaded {len(cities)} cities")
    w  = WorkspaceClient(profile=PROFILE)
    print(f"  Warehouse ID: {WAREHOUSE_ID}")
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"  run_ts: {run_ts}\n")

    print("Ingesting weather forecast (sunshine_duration, 14 days)...")
    for c in cities:
        url, payload = http_get(WEATHER_BASE, {
            "latitude": c["lat"], "longitude": c["lon"],
            "daily": "sunshine_duration", "forecast_days": 14,
            "timezone": "Europe/Oslo"
        })
        insert_row(w, WAREHOUSE_ID, WEATHER_TABLE, run_ts, c["city"], c["lat"], c["lon"], url, payload)
        print(f"  ✓ {c['city']}")

    print("\nIngesting air quality forecast (pm2_5 + european_aqi, 7 days)...")
    print("  [Note] Open-Meteo Air Quality API max forecast_days = 7")
    for c in cities:
        url, payload = http_get(AIR_BASE, {
            "latitude": c["lat"], "longitude": c["lon"],
            "hourly": "pm2_5,european_aqi", "forecast_days": 7,
            "timezone": "Europe/Oslo"
        })
        insert_row(w, WAREHOUSE_ID, AIR_TABLE, run_ts, c["city"], c["lat"], c["lon"], url, payload)
        print(f"  ✓ {c['city']}")

    print(f"\nBronze ingestion complete. run_ts = {run_ts}")
    print(f"  {WEATHER_TABLE} → 8 rows")
    print(f"  {AIR_TABLE}     → 8 rows")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### A1.3 — Create `cop_demo/pipeline/src/norway_weather_etl/silver_weather_daily.py`

SDP Materialized View using the modern `pyspark.pipelines` (dp) API.
Reads Bronze weather, parses the daily JSON arrays, explodes to one row per
city per forecast day.

```python
"""
Silver: weather_daily – one row per city per forecast day (latest run_ts).
Source: cop_weather_demo.bronze.openmeteo_weather_raw
Output: cop_weather_demo.silver.weather_daily
Columns: run_ts, city, date DATE, sunshine_duration_seconds DOUBLE
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType, DoubleType, StringType, StructField, StructType
)

CATALOG = "cop_weather_demo"
BRONZE  = f"{CATALOG}.bronze.openmeteo_weather_raw"

_SCHEMA = StructType([StructField("daily", StructType([
    StructField("time",              ArrayType(StringType()), True),
    StructField("sunshine_duration", ArrayType(DoubleType()), True),
]), True)])

@dp.materialized_view(
    name=f"{CATALOG}.silver.weather_daily",
    comment="Daily weather per city, latest run_ts only. Source: Open-Meteo /v1/forecast, 14-day horizon."
)
def silver_weather_daily():
    raw = spark.sql(f"""
        SELECT run_ts, city, payload_json FROM {BRONZE}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {BRONZE})
    """)
    parsed = (raw
        .withColumn("p",        F.from_json(F.col("payload_json"), _SCHEMA))
        .withColumn("time_arr", F.col("p.daily.time"))
        .withColumn("sun_arr",  F.col("p.daily.sunshine_duration")))
    exploded = parsed.select(
        F.col("run_ts"), F.col("city"), F.col("sun_arr"),
        F.posexplode("time_arr").alias("pos", "date_str")
    )
    return (exploded
        .withColumn("sunshine_duration_seconds", F.col("sun_arr").getItem(F.col("pos")))
        .select(
            F.col("run_ts"), F.col("city"),
            F.col("date_str").cast("date").alias("date"),
            F.col("sunshine_duration_seconds")
        ))
```

### A1.4 — Create `cop_demo/pipeline/src/norway_weather_etl/silver_air_hourly.py`

```python
"""
Silver: air_hourly – one row per city per forecast hour (latest run_ts).
Source: cop_weather_demo.bronze.openmeteo_air_raw
Output: cop_weather_demo.silver.air_hourly
Columns: run_ts, city, ts TIMESTAMP, pm2_5 DOUBLE, european_aqi DOUBLE
Note: horizon = 7 days (168 hours) — Open-Meteo Air Quality API max.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType, DoubleType, StringType, StructField, StructType
)

CATALOG = "cop_weather_demo"
BRONZE  = f"{CATALOG}.bronze.openmeteo_air_raw"

_SCHEMA = StructType([StructField("hourly", StructType([
    StructField("time",         ArrayType(StringType()), True),
    StructField("pm2_5",        ArrayType(DoubleType()), True),
    StructField("european_aqi", ArrayType(DoubleType()), True),
]), True)])

@dp.materialized_view(
    name=f"{CATALOG}.silver.air_hourly",
    comment="Hourly air quality per city, latest run_ts only. Source: Open-Meteo /v1/air-quality, 7-day horizon (API max)."
)
def silver_air_hourly():
    raw = spark.sql(f"""
        SELECT run_ts, city, payload_json FROM {BRONZE}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {BRONZE})
    """)
    parsed = (raw
        .withColumn("p",       F.from_json(F.col("payload_json"), _SCHEMA))
        .withColumn("time_arr", F.col("p.hourly.time"))
        .withColumn("pm25_arr", F.col("p.hourly.pm2_5"))
        .withColumn("aqi_arr",  F.col("p.hourly.european_aqi")))
    exploded = parsed.select(
        F.col("run_ts"), F.col("city"),
        F.col("pm25_arr"), F.col("aqi_arr"),
        F.posexplode("time_arr").alias("pos", "ts_str")
    )
    return (exploded
        .withColumn("pm2_5",        F.col("pm25_arr").getItem(F.col("pos")))
        .withColumn("european_aqi", F.col("aqi_arr").getItem(F.col("pos")))
        .select(
            F.col("run_ts"), F.col("city"),
            F.to_timestamp(F.col("ts_str"), "yyyy-MM-dd'T'HH:mm").alias("ts"),
            F.col("pm2_5"), F.col("european_aqi")
        ))
```

### A1.5 — Create `cop_demo/pipeline/src/norway_weather_etl/gold_sunshine_14d_rank.py`

```python
"""
Gold: sunshine_14d_rank – total 14-day sunshine hours per city, ranked DESC.
Source: cop_weather_demo.silver.weather_daily
Output: cop_weather_demo.gold.sunshine_14d_rank
Columns: run_ts, city, sunshine_hours_14d DOUBLE, rank INT
Metric: sunshine_hours_14d = SUM(sunshine_duration_seconds) / 3600. rank=1 = sunniest.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = "cop_weather_demo"
SILVER  = f"{CATALOG}.silver.weather_daily"

@dp.materialized_view(
    name=f"{CATALOG}.gold.sunshine_14d_rank",
    comment="14-day sunshine ranking. rank=1 is sunniest. Filter to MAX(run_ts) for current snapshot."
)
def gold_sunshine_14d_rank():
    silver = spark.sql(f"""
        SELECT run_ts, city, sunshine_duration_seconds FROM {SILVER}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {SILVER})
    """)
    window = Window.partitionBy("run_ts").orderBy(F.col("sunshine_hours_14d").desc())
    return (silver
        .groupBy("run_ts", "city")
        .agg((F.sum("sunshine_duration_seconds") / F.lit(3600.0)).alias("sunshine_hours_14d"))
        .withColumn("rank", F.rank().over(window)))
```

### A1.6 — Create `cop_demo/pipeline/src/norway_weather_etl/gold_clean_air_rank.py`

```python
"""
Gold: clean_air_rank – 7-day avg PM2.5 and European AQI per city, dual-ranked ASC.
Source: cop_weather_demo.silver.air_hourly
Output: cop_weather_demo.gold.clean_air_rank
Columns: run_ts, city, avg_pm2_5_horizon DOUBLE, avg_european_aqi_horizon DOUBLE,
         rank_pm25 INT, rank_aqi INT
Metric: rank_pm25=1 is cleanest by PM2.5. rank_aqi=1 is cleanest by AQI. Independent rankings.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = "cop_weather_demo"
SILVER  = f"{CATALOG}.silver.air_hourly"

@dp.materialized_view(
    name=f"{CATALOG}.gold.clean_air_rank",
    comment="7-day air quality ranking. rank_pm25=1 and rank_aqi=1 are cleanest. Independent rankings. Filter to MAX(run_ts)."
)
def gold_clean_air_rank():
    silver = spark.sql(f"""
        SELECT run_ts, city, pm2_5, european_aqi FROM {SILVER}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {SILVER})
    """)
    w_pm25 = Window.partitionBy("run_ts").orderBy(F.col("avg_pm2_5_horizon").asc())
    w_aqi  = Window.partitionBy("run_ts").orderBy(F.col("avg_european_aqi_horizon").asc())
    return (silver
        .groupBy("run_ts", "city")
        .agg(
            F.avg("pm2_5").alias("avg_pm2_5_horizon"),
            F.avg("european_aqi").alias("avg_european_aqi_horizon")
        )
        .withColumn("rank_pm25", F.rank().over(w_pm25))
        .withColumn("rank_aqi",  F.rank().over(w_aqi)))
```

### A1.7 — Create `cop_demo/pipeline/resources/norway_weather_etl.pipeline.yml`

```yaml
resources:
  pipelines:
    norway_weather_etl:
      name: norway_weather_etl
      description: >
        Norway 8-city weather intelligence. Reads Bronze API snapshots and
        produces Silver (normalised) + Gold (ranked) materialized views.
      catalog: cop_weather_demo
      target: silver
      serverless: true
      development: false
      libraries:
        - file:
            path: ../src/norway_weather_etl/silver_weather_daily.py
        - file:
            path: ../src/norway_weather_etl/silver_air_hourly.py
        - file:
            path: ../src/norway_weather_etl/gold_sunshine_14d_rank.py
        - file:
            path: ../src/norway_weather_etl/gold_clean_air_rank.py
```

### A1.8 — Create `cop_demo/notebooks/00_demo_driver.py`

Validation-only notebook. No build logic — all build is in this prompt.

```python
# Databricks notebook source
# Norway Weather Demo – Validation Notebook
# Run cells individually at each gate to spot-check a layer.
# COMMAND ----------
CATALOG = "cop_weather_demo"
# COMMAND ----------
# Gate 1: Bronze counts
display(spark.sql(f"""
  SELECT source, COUNT(*) AS row_count, MAX(run_ts) AS latest_run_ts FROM (
    SELECT 'weather'     AS source, run_ts FROM {CATALOG}.bronze.openmeteo_weather_raw
    UNION ALL
    SELECT 'air_quality' AS source, run_ts FROM {CATALOG}.bronze.openmeteo_air_raw
  ) GROUP BY source
"""))  # Expected: weather=8, air_quality=8
# COMMAND ----------
# Gate 2: Silver counts
display(spark.sql(f"""
  SELECT 'weather_daily' AS tbl, COUNT(*) AS rows, COUNT(DISTINCT city) AS cities
  FROM {CATALOG}.silver.weather_daily
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.silver.weather_daily)
  UNION ALL
  SELECT 'air_hourly', COUNT(*), COUNT(DISTINCT city)
  FROM {CATALOG}.silver.air_hourly
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.silver.air_hourly)
"""))  # Expected: 112 rows / 8 cities; ~1344 rows / 8 cities
# COMMAND ----------
# Gate 3a – Q1: Sunniest city (14-day forecast)
display(spark.sql(f"""
  SELECT rank, city, ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d
  FROM   {CATALOG}.gold.sunshine_14d_rank
  WHERE  run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.gold.sunshine_14d_rank)
  ORDER  BY rank
"""))
# COMMAND ----------
# Gate 3b – Q2: Cleanest air (7-day horizon)
display(spark.sql(f"""
  SELECT rank_pm25, rank_aqi, city,
         ROUND(avg_pm2_5_horizon, 2) AS avg_pm25_ug_m3,
         ROUND(avg_european_aqi_horizon, 1) AS avg_european_aqi
  FROM   {CATALOG}.gold.clean_air_rank
  WHERE  run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.gold.clean_air_rank)
  ORDER  BY rank_pm25
"""))
# COMMAND ----------
# ── POST-DEMO CLEANUP – run cells below individually as needed ──
# COMMAND ----------
# Option 1: Reset Bronze only (Silver/Gold rebuild automatically on next pipeline run)
# spark.sql(f"TRUNCATE TABLE {CATALOG}.bronze.openmeteo_weather_raw")
# spark.sql(f"TRUNCATE TABLE {CATALOG}.bronze.openmeteo_air_raw")
# print("Bronze truncated. Ready for fresh ingestion.")
# COMMAND ----------
# Option 2: Full teardown – drops catalog + all schemas + all tables
# spark.sql(f"DROP CATALOG IF EXISTS {CATALOG} CASCADE")
# print(f"Catalog {CATALOG} dropped.")
# COMMAND ----------
# Option 3: Destroy bundle pipeline from workspace
# import subprocess
# result = subprocess.run(
#     ["databricks", "bundle", "destroy", "--target", "dev", "--profile", "YOUR_PROFILE"],
#     capture_output=True, text=True
# )
# print(result.stdout or result.stderr)
# COMMAND ----------
# Option 4: Remove local files created during demo
# import shutil
# for p in ["cop_demo/data", "cop_demo/scripts", "cop_demo/pipeline/src",
#           "cop_demo/pipeline/resources", "cop_demo/notebooks"]:
#     shutil.rmtree(p, ignore_errors=True)
# print("Demo files removed.")
```

---

## A2 — Create Unity Catalog Objects

After A2 is implemented, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A2 UC catalog/schemas/tables` to `Done` or `Failed`

Use the `execute_sql` MCP tool. Run statements in order.

Execution rule (mandatory):
- Do NOT execute dependent DDL in parallel.
- For A2.1 -> A2.4, run statements sequentially in order (catalog, schemas, reference table/data, raw tables).
- If using `mcp_databricks_execute_sql_multi`, set `max_workers=1`.

If MCP SQL execution fails, fallback to CLI once using the same SQL via:

```bash
databricks sql statement-execution execute-statement --profile YOUR_PROFILE --warehouse-id YOUR_WAREHOUSE_ID --statement "<same-sql>"
```

### A2.1 — Catalog

```sql
CREATE CATALOG IF NOT EXISTS cop_weather_demo
COMMENT 'Norway Weather Demo – 8-city sunshine and air quality analysis (Open-Meteo)';
```

### A2.2 — Schemas

```sql
CREATE SCHEMA IF NOT EXISTS cop_weather_demo.bronze
COMMENT 'Raw Open-Meteo API JSON snapshots – append-only, one row per city per run_ts';

CREATE SCHEMA IF NOT EXISTS cop_weather_demo.silver
COMMENT 'Normalised rows – one per city per forecast period, latest run_ts';

CREATE SCHEMA IF NOT EXISTS cop_weather_demo.gold
COMMENT 'Rankings and aggregations – consumption-ready for dashboard and Genie';
```

### A2.3 — Reference cities table + data (idempotent)

```sql
CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.ref_cities (
  city STRING NOT NULL COMMENT 'Norwegian city name',
  lat  DOUBLE NOT NULL COMMENT 'Latitude WGS84 – hardcoded, no live geocoding',
  lon  DOUBLE NOT NULL COMMENT 'Longitude WGS84 – hardcoded, no live geocoding'
)
COMMENT 'Fixed city coordinates. Source: standard geographic coordinates for Norwegian city centres.';

INSERT INTO cop_weather_demo.bronze.ref_cities
SELECT city, lat, lon FROM (VALUES
  ('Bergen',       60.3913,  5.3221),
  ('Oslo',         59.9139, 10.7522),
  ('Trondheim',    63.4305, 10.3951),
  ('Stavanger',    58.9700,  5.7331),
  ('Tromsø',       69.6492, 18.9553),
  ('Kristiansand', 58.1599,  8.0182),
  ('Ålesund',      62.4722,  6.1495),
  ('Bodø',         67.2804, 14.4049)
) AS t(city, lat, lon)
WHERE NOT EXISTS (SELECT 1 FROM cop_weather_demo.bronze.ref_cities);
```

### A2.4 — Bronze raw tables

```sql
CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.openmeteo_weather_raw (
  run_ts       TIMESTAMP NOT NULL COMMENT 'UTC snapshot timestamp for this demo run',
  city         STRING    NOT NULL COMMENT 'City name matching ref_cities',
  lat          DOUBLE    NOT NULL,
  lon          DOUBLE    NOT NULL,
  request_url  STRING    NOT NULL COMMENT 'Full Open-Meteo forecast URL called',
  payload_json STRING    NOT NULL COMMENT 'Raw JSON response body'
)
COMMENT 'Bronze: Open-Meteo /v1/forecast. Append-only. One row per city per run_ts.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false');

CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.openmeteo_air_raw (
  run_ts       TIMESTAMP NOT NULL COMMENT 'UTC snapshot timestamp for this demo run',
  city         STRING    NOT NULL,
  lat          DOUBLE    NOT NULL,
  lon          DOUBLE    NOT NULL,
  request_url  STRING    NOT NULL COMMENT 'Full Open-Meteo air-quality URL called',
  payload_json STRING    NOT NULL COMMENT 'Raw JSON response body'
)
COMMENT 'Bronze: Open-Meteo /v1/air-quality. Append-only. One row per city per run_ts.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false');
```

Verify with `mcp_databricks_execute_sql`:

```sql
SELECT table_schema, table_name
FROM   cop_weather_demo.information_schema.tables
WHERE  table_schema IN ('bronze','silver','gold')
ORDER  BY table_schema, table_name;
```

---

## [GO/NO-GO GATE 1 — CATALOG + TABLES READY]

Immediately update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A2 UC catalog/schemas/tables` to `Done` or `Failed`
- Set `Gate 1 Catalog + tables ready` to `Done` or `Failed`

Present these results to the presenter:

> **Gate 1:**
> - Catalog `cop_weather_demo` exists ✓
> - Schemas bronze / silver / gold ✓
> - `ref_cities`: 8 rows ✓  |  `openmeteo_weather_raw`: 0 rows (expected) ✓  |  `openmeteo_air_raw`: 0 rows ✓
>
> **"GO" → Bronze ingestion (16 Open-Meteo API calls)**
> **"NO" → Investigate errors above**

---

## A3 — Update Bundle Config and Deploy

After A3 is implemented, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A3 Bundle validate + deploy` to `Done` or `Failed`

### A3.1 — Update `databricks.yml`

Add the pipeline include to the bundle root config:

```yaml
bundle:
  name: databricks codespace

include:
  - cop_demo/pipeline/resources/*.pipeline.yml

targets:
  dev:
    mode: production
    default: true
    workspace:
      host: https://dbc-YOUR_INSTANCE_ID.cloud.databricks.com
```

Use `mode: production` for this demo target to keep resource names stable and avoid user-prefixed names/tags.

### A3.2 — Validate bundle

```bash
databricks bundle validate --profile YOUR_PROFILE
```

Expected output contains `norway_weather_etl` with no errors. Fix any path
or YAML issues before proceeding.

Tool policy note: CLI primary for A3 (no equivalent MCP for DAB validate).

### A3.3 — Deploy bundle

```bash
databricks bundle deploy --target dev --profile YOUR_PROFILE
```

If deploy fails with `pipeline name is already used`, delete the old conflicting
pipeline first (or destroy prior bundle state), then re-run deploy so only one
`norway_weather_etl` pipeline remains.

Show the presenter: open Databricks UI → Pipelines tab →
`norway_weather_etl` pipeline now exists, never run, no tables yet.

Tool policy note: CLI primary for A3 (no equivalent MCP for DAB deploy).

---

## A4 — Bronze API Ingestion

Run the ingestion script:

```bash
cd "/Users/debanayak/Library/CloudStorage/OneDrive-Capgemini/Code Workspace/databricks codespace"
test -x "/Users/debanayak/.ai-dev-kit/.venv/bin/python"
/Users/debanayak/.ai-dev-kit/.venv/bin/python -c "import sys; print(sys.executable)"
/Users/debanayak/.ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py
```


Script performs:
1. Reads `cop_demo/data/cities.json` — 8 cities, hardcoded lat/lon
2. Calls `https://api.open-meteo.com/v1/forecast?daily=sunshine_duration&forecast_days=14&timezone=Europe/Oslo` × 8
3. Calls `https://air-quality-api.open-meteo.com/v1/air-quality?hourly=pm2_5,european_aqi&forecast_days=7&timezone=Europe/Oslo` × 8
4. Inserts 1 row per city into each Bronze table via SDK statement execution

Verify with `execute_sql`:

```sql
SELECT source, COUNT(*) AS row_count, MAX(run_ts) AS latest_run_ts
FROM (
  SELECT 'weather'     AS source, run_ts FROM cop_weather_demo.bronze.openmeteo_weather_raw
  UNION ALL
  SELECT 'air_quality' AS source, run_ts FROM cop_weather_demo.bronze.openmeteo_air_raw
)
GROUP BY source;
```

Expected: `weather = 8`, `air_quality = 8`.

---

## [GO/NO-GO GATE 2 — BRONZE POPULATED]

Immediately update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A4 Bronze ingestion` to `Done` or `Failed`
- Set `Gate 2 Bronze populated` to `Done` or `Failed`

> **Gate 2:**
> - `openmeteo_weather_raw`: 8 rows, `run_ts = {value}` ✓
> - `openmeteo_air_raw`: 8 rows, `run_ts = {value}` ✓
> - Bronze layer is immutable for this `run_ts` — safe to re-run pipeline without re-calling APIs.
>
> **"GO" → Trigger SDP pipeline (Silver + Gold)**
> **"NO" → Inspect Bronze payloads or re-run ingestion**

---

## A5 — Run SDP Pipeline

Trigger with MCP first:

1. Resolve deployed pipeline id (bundle names are often target-prefixed):
  - Use `mcp_databricks_manage_pipeline` with `action=find_by_name` and name `norway_weather_etl`.
  - If not found, list pipelines and pick the one whose name ends with `norway_weather_etl`.
  - Never hardcode or match any user handle in object names.
2. Start run using `mcp_databricks_manage_pipeline_run` with:
  - `action=start`
  - `wait=true`
  - `full_refresh=false`

CLI fallback (only if MCP start fails):

```bash
databricks bundle run norway_weather_etl --profile YOUR_PROFILE
```

### A5.1 — Blocker Self-Heal: `LIBRARY_FILE_NOT_FOUND` (Mandatory)

If the pipeline run fails with `LIBRARY_FILE_NOT_FOUND`, apply this recovery flow immediately:

1. Read pipeline run error details (`mcp_databricks_manage_pipeline_run` with `action=get`, `full_error_details=true`).
2. Extract the missing workspace file path from the error text.
3. Derive the target folder as the parent directory of that missing file path.
4. Upload the four ETL files to that exact folder using `mcp_databricks_manage_workspace_files`:

```text
action=upload
workspace_path=<derived_parent_folder>
local_path=/Users/debanayak/Library/CloudStorage/OneDrive-Capgemini/Code Workspace/databricks codespace/cop_demo/pipeline/src/norway_weather_etl/*.py
overwrite=true
```

5. Re-run pipeline start once (`mcp_databricks_manage_pipeline_run`, `action=start`, `wait=true`).
6. If re-run returns an active update already exists (or MCP returns a response-parsing error but an update id is available), poll that update id using `mcp_databricks_manage_pipeline_run` `action=get` until terminal state before attempting CLI fallback.
7. Only use CLI fallback when no active update is running.

Rules:

- Do not hardcode any user-specific path segment.
- Always derive workspace path from the actual error payload.
- Record the blocker and recovery action in checklist notes.

While running (~90 sec on serverless): switch to Databricks UI → Pipelines →
`norway_weather_etl` and show the live DAG. Four materialized views process
in dependency order:

1. `silver.weather_daily`   → 112 rows (8 × 14 days)
2. `silver.air_hourly`      → ~1 344 rows (8 × 168 hours)
3. `gold.sunshine_14d_rank` → 8 rows (ranked 1–8)
4. `gold.clean_air_rank`    → 8 rows (ranked 1–8)

After pipeline completes, verify layer counts with `mcp_databricks_execute_sql`:

```sql
SELECT 'silver_weather' AS layer, COUNT(*) AS rows
FROM   cop_weather_demo.silver.weather_daily
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.silver.weather_daily)
UNION ALL
SELECT 'silver_air',    COUNT(*)
FROM   cop_weather_demo.silver.air_hourly
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.silver.air_hourly)
UNION ALL
SELECT 'gold_sunshine', COUNT(*)
FROM   cop_weather_demo.gold.sunshine_14d_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
UNION ALL
SELECT 'gold_air',      COUNT(*)
FROM   cop_weather_demo.gold.clean_air_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank);
```

Then reveal the demo answers:

```sql
-- Q1: Sunniest city
SELECT rank, city, ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d
FROM   cop_weather_demo.gold.sunshine_14d_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
ORDER  BY rank;
```

```sql
-- Q2: Cleanest air
SELECT rank_pm25, rank_aqi, city,
       ROUND(avg_pm2_5_horizon, 2)        AS avg_pm25_ug_m3,
       ROUND(avg_european_aqi_horizon, 1) AS avg_european_aqi
FROM   cop_weather_demo.gold.clean_air_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank)
ORDER  BY rank_pm25;
```

---

## [GO/NO-GO GATE 3 — GOLD POPULATED]

Immediately update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `A5 SDP pipeline run` to `Done` or `Failed`
- Set `Gate 3 Gold populated` to `Done` or `Failed`

> **Gate 3:**
> - Gold layer complete: 8 cities ranked for sunshine AND air quality.
> - Q1: **{rank-1 city}** is the sunniest — **{X}** hours over 14 days ✓
> - Q2: **{rank-1 city}** has cleanest air — avg PM2.5 = **{Y} µg/m³** over 7 days ✓
>
> **"GO" → Hand off to support-analytics-reporter for Dashboard + Genie**
> **"NO" → Inspect pipeline output or re-trigger**

---

## ════════════════════════════════════════════════════════
## PHASE B  ·  Analytics Reporter
## ════════════════════════════════════════════════════════

> Invoke the **Analytics Reporter** agent for all steps in Phase B.
> This agent uses the `databricks-aibi-dashboards` and `databricks-genie`
> skills plus Databricks MCP tools.

---

## B1 — Create AI/BI Dashboard

After B1 is implemented, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `B1 Dashboard build + publish` to `Done` or `Failed`

### B1.1 — Inspect Gold tables

Use `mcp_databricks_get_table_stats_and_schema` MCP tool for:
- `cop_weather_demo.gold.sunshine_14d_rank`
- `cop_weather_demo.gold.clean_air_rank`
- `cop_weather_demo.silver.weather_daily`

### B1.2 — Get warehouse

Do not call `get_best_warehouse`.
Use fixed `warehouse_id`: `YOUR_WAREHOUSE_ID` for all `mcp_databricks_execute_sql`,
`mcp_databricks_manage_dashboard` create_or_update, and publish actions in Phase B.

### B1.3 — Validate all dataset queries (mandatory — do not skip)

Test with `mcp_databricks_execute_sql`. Fix any failure before building the dashboard.

**Dataset `ds_sunshine_rank`** (bar chart):

```sql
SELECT run_ts, city, ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d, rank
FROM   cop_weather_demo.gold.sunshine_14d_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
ORDER  BY rank ASC
```

**Dataset `ds_daily_top3`** (daily breakdown table):

```sql
SELECT w.run_ts, w.city, w.date,
       ROUND(w.sunshine_duration_seconds / 3600.0, 2) AS sunshine_hours_day
FROM   cop_weather_demo.silver.weather_daily w
INNER JOIN (
  SELECT city FROM cop_weather_demo.gold.sunshine_14d_rank
  WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
    AND  rank <= 3
) top3 ON w.city = top3.city
WHERE  w.run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.silver.weather_daily)
ORDER  BY w.city, w.date
```

**Dataset `ds_clean_air`** (air quality time-series for line chart):

```sql
SELECT *
FROM   cop_weather_demo.silver.air_hourly
```

### B1.4 — Build dashboard

Use `mcp_databricks_manage_dashboard` with `action=create_or_update`:

- **Name**: `Norway Weather – 14-Day Sunshine & 7-Day Air Quality`
- **3 datasets**: `ds_sunshine_rank`, `ds_daily_top3`, `ds_clean_air`
- **3 widgets**:
  - **Visual 1** — Horizontal bar chart
    - Dataset: `ds_sunshine_rank`  |  X: `city`  |  Y: `sunshine_hours_14d` (sorted desc)
    - Title: `Sunshine Hours – 14-Day Forecast`
  - **Visual 2** — Table
    - Dataset: `ds_daily_top3`  |  Columns: `city`, `date`, `sunshine_hours_day`
    - Title: `Daily Sunshine – Top 3 Cities`
  - **Visual 3** — Time-series line chart (with markers)
    - Dataset: `ds_clean_air`
    - Chart type: Line chart with markers
    - Columns:
      - X-axis: `ts` (temporal scale, display label `Time`)
      - Y-axis: `pm2_5` (quantitative scale, display label `PM2.5`)
      - Series/grouping: `city`
    - Title: `Air Quality Over Time`
    - Layout requirements:
      - Add a city filter widget (single-select dropdown)
      - Filter title: `Select City`
      - Filter field: `city`
      - Filter position: top-left, 2 columns wide, 3 rows tall
      - Place the line chart to the right of the filter, 10 columns wide, 7 rows tall
      - Ensure the line chart cross-filters from the city selection
    - Style requirements:
      - Show continuous line with visible data point markers
      - Include legend for cities
      - Use hourly time progression on X-axis
      - Y-axis labeled as PM2.5
      - Display trends clearly, not tabular data  
- **Filters**: `city` multi-select (mandatory for Visual 3)

### B1.5 — Publish dashboard

Use `mcp_databricks_manage_dashboard` with `action=publish`.

CLI fallback (only if MCP dashboard calls fail):

```bash
databricks dashboards get "$DASHBOARD_ID" --profile YOUR_PROFILE
```

Note the public URL.

---

## [GO/NO-GO GATE 4 — DASHBOARD LIVE]

Immediately update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `B1 Dashboard build + publish` to `Done` or `Failed`
- Set `Gate 4 Dashboard live` to `Done` or `Failed`

> **Gate 4:**
> - Dashboard published: **{URL}** ✓
> - Visual 1: 8 cities in sunshine bar chart ✓
> - Visual 2: Daily breakdown for top-3 cities ✓
> - Visual 3: hourly PM2.5 trend line (7-day horizon) with city filter ✓
>
> **"GO" → Create Genie Space**
> **"NO" → Fix widget field name mismatches or re-validate queries**

---

## B2 — Create Genie Space

After B2 is implemented, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `B2 Genie space + smoke tests` to `Done` or `Failed`

Use `mcp_databricks_manage_genie` with `action=create_or_update` and the following parameters verbatim.

**display_name**: `Norway Weather Intelligence`

**table_identifiers** (4 tables):
```
cop_weather_demo.gold.sunshine_14d_rank
cop_weather_demo.gold.clean_air_rank
cop_weather_demo.silver.weather_daily
cop_weather_demo.silver.air_hourly
```

**description**:
```
Norway 8-city weather intelligence: 14-day sunshine forecasts and 7-day air quality analysis.
Data sourced from Open-Meteo API and snapshotted at run_ts. Always filter to MAX(run_ts).
Cities in scope: Bergen, Oslo, Trondheim, Stavanger, Tromsø, Kristiansand, Ålesund, Bodø.
```

**instructions** (include verbatim — these guide Genie's SQL generation):
```
METRIC DEFINITIONS

"Sunniest city" = city where rank = 1 in gold.sunshine_14d_rank (highest sunshine_hours_14d).
  sunshine_hours_14d = SUM(sunshine_duration_seconds) / 3600.0 across 14 daily forecast rows.
  Ranked DESCENDING — rank=1 is best (most sunshine).

"Cleanest air" = city where rank_pm25 = 1 in gold.clean_air_rank (lowest avg_pm2_5_horizon).
  avg_pm2_5_horizon = AVG(pm2_5) across all 168 hourly forecast rows (7-day horizon).
  rank_pm25 (PM2.5) and rank_aqi (European AQI) are INDEPENDENT rankings — both ASC, 1=cleanest.

HORIZON
  Sunshine horizon = 14 days.
  Air quality horizon = 7 days (maximum supported by Open-Meteo Air Quality API).
  When a user asks "next 7 days" for air quality, this is the complete available horizon.

DATA FRESHNESS
  Always filter to MAX(run_ts) unless the user asks for historical or multi-run comparison.
  run_ts identifies the demo session snapshot. Do not join across different run_ts values.

QUERY PATTERNS

For "sunniest city":
  SELECT city, sunshine_hours_14d, rank
  FROM cop_weather_demo.gold.sunshine_14d_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
  ORDER BY rank LIMIT 1

For "cleanest air (PM2.5)":
  SELECT city, avg_pm2_5_horizon, rank_pm25
  FROM cop_weather_demo.gold.clean_air_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank)
  ORDER BY rank_pm25 LIMIT 1

For city comparison (e.g. Bergen vs Oslo):
  SELECT s.city, s.sunshine_hours_14d, s.rank AS sunshine_rank,
         a.avg_pm2_5_horizon, a.rank_pm25
  FROM cop_weather_demo.gold.sunshine_14d_rank s
  JOIN cop_weather_demo.gold.clean_air_rank    a USING (run_ts, city)
  WHERE s.run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
    AND s.city IN ('Bergen','Oslo')
```

**sample_questions** (4 seed questions):
1. `Which is the sunniest city in Norway for the next 14 days?`
2. `Rank all cities by sunshine hours over the next 14 days.`
3. `Which city has the cleanest air for the next 7 days (PM2.5)?`
4. `Compare Bergen vs Oslo for sunshine and PM2.5.`

Note the `space_id` returned.

### B2.1 — Smoke-test with `mcp_databricks_ask_genie`

Use `mcp_databricks_ask_genie` with the `space_id`. Ask all 4 seed questions.
Verify:
- Q1 returns a specific city name + hours
- Q2 returns a ranked list of all 8 cities
- Q3 returns a specific city name + PM2.5 µg/m³ value
- Q4 returns a two-row comparison table

CLI fallback (only if MCP Genie calls fail):

```bash
databricks genie-spaces get "$SPACE_ID" --profile YOUR_PROFILE
```

---

## [GO/NO-GO GATE 5 — GENIE SPACE LIVE]

Immediately update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `B2 Genie space + smoke tests` to `Done` or `Failed`
- Set `Gate 5 Genie live` to `Done` or `Failed`

> **Gate 5:**
> - Genie Space created: **{URL}** ✓
> - 4 seed questions visible ✓
> - Smoke Q1: **{city}** is sunniest with **{X}** hours ✓
> - Smoke Q3: **{city}** has cleanest air, avg PM2.5 = **{Y} µg/m³** ✓
>
> **"GO" → Live Q&A finale with audience**
> **"NO" → Re-check curated instructions or re-test Genie queries**

---

## B3 — Live Demo Q&A Finale

After completing finale Q&A, update `cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md`:
- Set `B3 Live Q&A finale` to `Done` or `Failed`
- Set `Run End Time`

Ask these questions in the Genie Space browser UI (or via `mcp_databricks_ask_genie`):

```
Q1 – "Which is the sunniest city in Norway for the next 14 days?"
```
→ Show city name + sunshine hours + Genie-generated bar chart

```
Q2 – "Which city has the cleanest air in the next 7 days?"
```
→ Show city name + PM2.5 value + generated SQL

```
Bonus – "Compare Bergen vs Oslo for sunshine and PM2.5."
```
→ Show two-row comparison table

---

