---
mode: agent
description: >
  Norway Weather Live Demo – Full live build for Databricks.
  Creates catalog cop_weather_demo, schemas, Bronze tables, ingests
  Open-Meteo API data, deploys SDP pipeline, creates AI/BI Dashboard
  and Genie Space. Entirely orchestrated by this prompt in agent mode –
  no manual Databricks UI steps required beyond GO/NO-GO gates.
---

# Norway Weather Demo – Agent Mode Build Prompt

> **How to run**: Open this file in VS Code, click **"Run Prompt"** in
> GitHub Copilot Chat (Agent Mode). The agent executes every step using
> Databricks MCP tools and terminal commands. At each **[GO/NO-GO GATE]**,
> it pauses and presents results — you type **GO** or **NO** to continue
> or troubleshoot.
>
> **Nothing is pre-built.** The entire demo is constructed start-to-finish
> from this prompt. Re-running is safe: each run creates a new `run_ts`
> snapshot without dropping existing data. To start completely fresh, run
> the cleanup step at the end.

---

## Environment

| Setting | Value |
|---------|-------|
| Workspace | `https://dbc-b74acda9-4dbe.cloud.databricks.com` |
| Auth profile | `dbx_free` |
| Repo root | `{workspace_folder}` (auto-resolved by agent) |
| Catalog to create | `cop_weather_demo` |
| Bundle target | `dev` |

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

---

## STEP 0 — Pre-flight: Verify Authentication

Run in terminal:

```bash
databricks auth status --profile dbx_free
```

If the output does **not** show `✓ authenticated`, run:

```bash
databricks auth login --profile dbx_free
```

Wait for the browser OAuth flow to complete before proceeding.

---

## STEP 1 — Deploy Databricks Asset Bundle

Deploy the pipeline resource to the workspace. This creates the
`norway_weather_etl` pipeline definition without running it.

```bash
cd "{workspace_folder}"
databricks bundle deploy --target dev --profile dbx_free
```

Confirm output contains `norway_weather_etl` deployed successfully.
Show the presenter the pipeline in the Databricks UI (Pipelines tab) — it
exists but has never run. All data layers are still empty.

---

## STEP 2 — Create Unity Catalog: Catalog + Schemas + Tables

Use the `execute_sql` MCP tool to run each statement below **in order**.

### 2a — Create Catalog

```sql
CREATE CATALOG IF NOT EXISTS cop_weather_demo
COMMENT 'Norway Weather Demo – 8-city sunshine and air quality analysis (Open-Meteo)';
```

### 2b — Create Schemas

```sql
CREATE SCHEMA IF NOT EXISTS cop_weather_demo.bronze
COMMENT 'Raw Open-Meteo API JSON snapshots, one row per city per run_ts';

CREATE SCHEMA IF NOT EXISTS cop_weather_demo.silver
COMMENT 'Normalized weather and air quality rows, one per city per time period';

CREATE SCHEMA IF NOT EXISTS cop_weather_demo.gold
COMMENT 'Rankings and aggregations ready for dashboard and Genie Space';
```

### 2c — Create Reference Cities Table (static, no geocoding)

```sql
CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.ref_cities (
  city  STRING NOT NULL COMMENT 'Norwegian city name',
  lat   DOUBLE NOT NULL COMMENT 'Latitude  WGS84 – hardcoded, no live geocoding',
  lon   DOUBLE NOT NULL COMMENT 'Longitude WGS84 – hardcoded, no live geocoding'
)
COMMENT 'Fixed city coordinate reference. Source: standard geographic coordinates.';
```

### 2d — Populate ref_cities (idempotent)

```sql
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

Verify:

```sql
SELECT COUNT(*) AS city_count FROM cop_weather_demo.bronze.ref_cities;
-- Expected: 8
```

### 2e — Create Bronze Raw Tables

```sql
CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.openmeteo_weather_raw (
  run_ts       TIMESTAMP NOT NULL COMMENT 'Demo run snapshot timestamp (UTC)',
  city         STRING    NOT NULL COMMENT 'City name from ref_cities',
  lat          DOUBLE    NOT NULL,
  lon          DOUBLE    NOT NULL,
  request_url  STRING    NOT NULL COMMENT 'Full Open-Meteo forecast URL used',
  payload_json STRING    NOT NULL COMMENT 'Raw JSON response body'
)
COMMENT 'Bronze: Open-Meteo /v1/forecast responses. Append-only. One row per city per run_ts.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false');

CREATE TABLE IF NOT EXISTS cop_weather_demo.bronze.openmeteo_air_raw (
  run_ts       TIMESTAMP NOT NULL COMMENT 'Demo run snapshot timestamp (UTC)',
  city         STRING    NOT NULL,
  lat          DOUBLE    NOT NULL,
  lon          DOUBLE    NOT NULL,
  request_url  STRING    NOT NULL COMMENT 'Full Open-Meteo Air Quality URL used',
  payload_json STRING    NOT NULL COMMENT 'Raw JSON response body'
)
COMMENT 'Bronze: Open-Meteo /v1/air-quality responses. Append-only. One row per city per run_ts.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false');
```

---

## [GO/NO-GO GATE 1 — CATALOG AND TABLES READY]

Run this verification query using `execute_sql`:

```sql
SELECT table_schema, table_name
FROM   cop_weather_demo.information_schema.tables
WHERE  table_schema IN ('bronze', 'silver', 'gold')
ORDER  BY table_schema, table_name;
```

Present to the presenter:

> **Gate 1 results:**
> - Catalog `cop_weather_demo` ✓
> - Schemas: bronze, silver, gold ✓
> - Bronze tables: ref_cities (8 rows), openmeteo_weather_raw (0), openmeteo_air_raw (0) ✓
>
> **Type GO to ingest Bronze data from Open-Meteo APIs.**
> **Type NO to review any errors above.**

---

## STEP 3 — Bronze API Ingestion

Run the Bronze ingestion script using the repo's virtual environment:

```bash
cd "{workspace_folder}"
.ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py
```

The script:
- Reads `cop_demo/data/cities.json` (8 Norwegian cities, hardcoded lat/lon)
- Calls `https://api.open-meteo.com/v1/forecast?daily=sunshine_duration&forecast_days=14&timezone=Europe/Oslo` for each city
- Calls `https://air-quality-api.open-meteo.com/v1/air-quality?hourly=pm2_5,european_aqi&forecast_days=7&timezone=Europe/Oslo` for each city
- Writes one row per city into each Bronze table via Databricks SQL statement execution
- Uses auth profile `dbx_free`

Expected terminal output:
```
Norway Weather Demo – Bronze Ingestion
  Cities file : .../cop_demo/data/cities.json
  Loaded 8 cities
  Warehouse   : <name> (<id>)
  run_ts      : 2026-05-04 HH:MM:SS
Ingesting weather forecast (sunshine_duration, 14 days)...
  ✓ Bergen  ✓ Oslo  ✓ Trondheim  ...  ✓ Bodø
Ingesting air quality forecast (pm2_5 + european_aqi, 7 days)...
  ✓ Bergen  ...  ✓ Bodø
Bronze ingestion complete.
  cop_weather_demo.bronze.openmeteo_weather_raw  →  8 rows
  cop_weather_demo.bronze.openmeteo_air_raw      →  8 rows
```

Verify via `execute_sql`:

```sql
SELECT source, COUNT(*) AS row_count, MAX(run_ts) AS latest_run_ts
FROM (
  SELECT 'weather'     AS source, run_ts FROM cop_weather_demo.bronze.openmeteo_weather_raw
  UNION ALL
  SELECT 'air_quality' AS source, run_ts FROM cop_weather_demo.bronze.openmeteo_air_raw
)
GROUP BY source;
-- Expected: weather=8, air_quality=8
```

---

## [GO/NO-GO GATE 2 — BRONZE POPULATED]

Present to the presenter:

> **Gate 2 results:**
> - `openmeteo_weather_raw`: 8 rows, run_ts = {value} ✓
> - `openmeteo_air_raw`: 8 rows, run_ts = {value} ✓
> - Raw Open-Meteo JSON snapshots captured. Bronze layer is immutable for this run_ts.
>
> **Type GO to trigger the SDP pipeline and build Silver + Gold.**
> **Type NO to inspect Bronze payloads or re-run ingestion.**

---

## STEP 4 — Run SDP Pipeline (Silver → Gold)

Trigger the Lakeflow Spark Declarative Pipeline:

```bash
databricks bundle run norway_weather_etl --profile dbx_free
```

The pipeline (serverless, ~90 sec) creates four materialized views:
1. `cop_weather_demo.silver.weather_daily`  (112 rows = 8 cities × 14 days)
2. `cop_weather_demo.silver.air_hourly`     (~1 344 rows = 8 cities × 168 hours)
3. `cop_weather_demo.gold.sunshine_14d_rank`  (8 rows, ranked 1–8)
4. `cop_weather_demo.gold.clean_air_rank`     (8 rows, ranked 1–8)

While waiting, switch to the Databricks UI → Pipelines → `norway_weather_etl`
to show the live pipeline DAG for the presenter.

Verify via `execute_sql` after completion:

```sql
SELECT 'silver_weather' AS layer, COUNT(*) AS rows
FROM   cop_weather_demo.silver.weather_daily
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.silver.weather_daily)
UNION ALL
SELECT 'silver_air',   COUNT(*)
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
-- Expected: 112, ~1344, 8, 8
```

Then show the demo answers via `execute_sql`:

```sql
-- Q1 Preview: Sunniest city (14-day forecast)
SELECT rank, city, ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d
FROM   cop_weather_demo.gold.sunshine_14d_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
ORDER  BY rank;
```

```sql
-- Q2 Preview: Cleanest air (7-day horizon)
SELECT rank_pm25, rank_aqi, city,
       ROUND(avg_pm2_5_horizon, 2)        AS avg_pm25_ug_m3,
       ROUND(avg_european_aqi_horizon, 1) AS avg_european_aqi
FROM   cop_weather_demo.gold.clean_air_rank
WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank)
ORDER  BY rank_pm25;
```

---

## [GO/NO-GO GATE 3 — GOLD POPULATED]

Present to the presenter:

> **Gate 3 results:**
> - Gold layer complete: 8 cities ranked for both sunshine and air quality.
> - Q1 answer: **{rank-1 city}** is the sunniest with **{X}** hours of sunshine over 14 days.
> - Q2 answer: **{rank-1 city}** has the cleanest air with avg PM2.5 = **{Y} µg/m³** over 7 days.
>
> **Type GO to create the AI/BI Dashboard.**
> **Type NO to inspect pipeline output or re-run.**

---

## STEP 5 — Create AI/BI Dashboard

### 5a — Inspect tables (mandatory pre-step)

Use `get_table_details` MCP tool for each of:
- `cop_weather_demo.gold.sunshine_14d_rank`
- `cop_weather_demo.gold.clean_air_rank`
- `cop_weather_demo.silver.weather_daily`

### 5b — Get warehouse ID

Use `get_best_warehouse` MCP tool. Note the warehouse ID for the dashboard.

### 5c — Validate all three dataset queries (mandatory — do NOT skip)

Test each query with `execute_sql` before building the dashboard.
If any query fails, fix it before proceeding.

**Dataset 1 — `ds_sunshine_rank`** (bar chart source):

```sql
SELECT
  city,
  ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d,
  rank
FROM cop_weather_demo.gold.sunshine_14d_rank
WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
ORDER BY rank ASC
```

**Dataset 2 — `ds_daily_top3`** (daily breakdown table source):

```sql
SELECT
  w.city,
  w.date,
  ROUND(w.sunshine_duration_seconds / 3600.0, 2) AS sunshine_hours_day
FROM cop_weather_demo.silver.weather_daily w
INNER JOIN (
  SELECT city
  FROM   cop_weather_demo.gold.sunshine_14d_rank
  WHERE  run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
    AND  rank   <= 3
) top3 ON w.city = top3.city
WHERE w.run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.silver.weather_daily)
ORDER BY w.city, w.date
```

**Dataset 3 — `ds_clean_air`** (air quality comparison source):

```sql
SELECT
  city,
  ROUND(avg_pm2_5_horizon, 2)        AS avg_pm25_ug_m3,
  ROUND(avg_european_aqi_horizon, 1) AS avg_european_aqi,
  rank_pm25,
  rank_aqi
FROM cop_weather_demo.gold.clean_air_rank
WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank)
ORDER BY rank_pm25 ASC
```

### 5d — Create the dashboard

Use `create_or_update_dashboard` MCP tool with:

**Name**: `Norway Weather – 14-Day Sunshine & 7-Day Air Quality`

**3 datasets** (using the validated queries above):
- `ds_sunshine_rank` → Dataset 1 query
- `ds_daily_top3`    → Dataset 2 query
- `ds_clean_air`     → Dataset 3 query

**3 widgets**:
- **Visual 1** – Horizontal bar chart
  - Dataset: `ds_sunshine_rank`
  - X-axis: `city`
  - Y-axis: `sunshine_hours_14d` (sort descending)
  - Title: `Sunshine Hours – 14-Day Forecast`
- **Visual 2** – Table widget
  - Dataset: `ds_daily_top3`
  - Columns: `city`, `date`, `sunshine_hours_day`
  - Title: `Daily Sunshine – Top 3 Cities`
- **Visual 3** – Table widget
  - Dataset: `ds_clean_air`
  - Columns: `rank_pm25`, `rank_aqi`, `city`, `avg_pm25_ug_m3`, `avg_european_aqi`
  - Title: `Air Quality Comparison – 7-Day Horizon`

**Parameter filter**: `run_ts` — applied to all 3 datasets (mandatory)
**Optional filter**: `city` — multi-select on all datasets

### 5e — Publish dashboard

Use `publish_dashboard` MCP tool with `publish=True`.
Note the dashboard URL from the response.

---

## [GO/NO-GO GATE 4 — DASHBOARD LIVE]

Present to the presenter:

> **Gate 4 results:**
> - Dashboard published: **{dashboard URL}**
> - Visual 1: Bar chart — 8 cities ranked by sunshine hours ✓
> - Visual 2: Daily breakdown for top-3 cities ✓
> - Visual 3: PM2.5 + AQI comparison for all 8 cities ✓
>
> **Type GO to create the Genie Space.**
> **Type NO to review dashboard visuals or fix widget errors.**

---

## STEP 6 — Create Genie Space

Use `create_or_update_genie` MCP tool with the following parameters exactly:

**display_name**: `Norway Weather Intelligence`

**table_identifiers**:
```
cop_weather_demo.gold.sunshine_14d_rank
cop_weather_demo.gold.clean_air_rank
cop_weather_demo.silver.weather_daily
cop_weather_demo.silver.air_hourly
```

**description**:
```
Norway 8-city weather intelligence: 14-day sunshine forecasts and 7-day air quality analysis.
Data sourced from Open-Meteo API, snapshotted at run_ts. Use run_ts to identify the current demo session.
Cities: Bergen, Oslo, Trondheim, Stavanger, Tromsø, Kristiansand, Ålesund, Bodø.
```

**instructions** (curated metric definitions — include verbatim):
```
METRIC DEFINITIONS:

"Sunniest city" = city where rank = 1 in gold.sunshine_14d_rank (highest sunshine_hours_14d).
sunshine_hours_14d = SUM(sunshine_duration_seconds) / 3600.0 across all 14 daily forecast rows per city.
Ranked DESCENDING: rank=1 is best (most sunshine).

"Cleanest air city" = city where rank_pm25 = 1 in gold.clean_air_rank (lowest avg_pm2_5_horizon).
avg_pm2_5_horizon = AVG(pm2_5) across all 168 forecast hours (7-day horizon).
rank_pm25 (PM2.5-based) and rank_aqi (European AQI-based) are INDEPENDENT rankings.
Ranked ASCENDING: rank=1 is best (lowest pollution).

HORIZON CONTEXT:
Sunshine data covers a 14-day forecast horizon.
Air quality data covers a 7-day forecast horizon (maximum supported by Open-Meteo Air Quality API).
When a user asks about "next 7 days" for air quality, this is the full available horizon.

DATA FRESHNESS:
Always filter to MAX(run_ts) unless the user explicitly asks for historical or multi-run comparison.
The run_ts column identifies the demo session in which data was captured.

QUERY PATTERNS:
For "sunniest city":
  SELECT city, sunshine_hours_14d, rank
  FROM cop_weather_demo.gold.sunshine_14d_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
  ORDER BY rank LIMIT 1

For "cleanest air city (PM2.5)":
  SELECT city, avg_pm2_5_horizon, rank_pm25
  FROM cop_weather_demo.gold.clean_air_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.clean_air_rank)
  ORDER BY rank_pm25 LIMIT 1

For city comparison (e.g. Bergen vs Oslo):
  SELECT city, sunshine_hours_14d, rank,
         avg_pm2_5_horizon, rank_pm25
  FROM cop_weather_demo.gold.sunshine_14d_rank s
  JOIN cop_weather_demo.gold.clean_air_rank a USING (run_ts, city)
  WHERE run_ts = (SELECT MAX(run_ts) FROM cop_weather_demo.gold.sunshine_14d_rank)
    AND city IN ('Bergen', 'Oslo')
```

**sample_questions**:
1. `Which is the sunniest city in Norway for the next 14 days?`
2. `Rank the cities by sunshine hours over the next 14 days.`
3. `Which city has the cleanest air for the next 7 days (PM2.5)?`
4. `Compare Bergen vs Oslo for sunshine and PM2.5.`

Note the `space_id` from the response — needed for the next step.

### 6a — Smoke-test Genie with seed questions

Use `ask_genie` MCP tool with the `space_id` returned above. Ask each seed question and verify:
- Q1 returns a specific Norwegian city name + sunshine hours
- Q2 returns a ranked list of 8 cities
- Q3 returns a specific city name + PM2.5 value
- Q4 returns a comparison table for Bergen and Oslo

---

## [GO/NO-GO GATE 5 — GENIE SPACE LIVE]

Present to the presenter:

> **Gate 5 results:**
> - Genie Space created: **{Genie URL}**
> - 4 seed questions visible in the space
> - Smoke-test Q1: **{city}** is the sunniest with **{X}** hours ✓
> - Smoke-test Q3: **{city}** has cleanest air, avg PM2.5 = **{Y} µg/m³** ✓
>
> **Type GO — Demo is live. Open Genie Space in browser for the Q&A finale.**
> **Type NO to re-test Genie or fix a query.**

---

## STEP 7 — Live Demo Q&A Finale

Ask these questions live via `ask_genie` (or the presenter types them directly
into the Genie Space in the browser):

```
Q1: "Which is the sunniest city in Norway for the next 14 days?"
```

```
Q2: "Which city has the cleanest air in the next 7 days?"
```

```
Bonus: "Compare Bergen vs Oslo for sunshine and PM2.5."
```

Show the Genie-generated SQL + result table + auto-chart for each answer.

---

## Timing Reference

| Step | Est. Time | Who |
|------|-----------|-----|
| 0–1: Auth + Bundle Deploy | ~1 min | Agent (terminal) |
| 2: Create UC catalog/schemas/tables | ~1 min | Agent (MCP execute_sql) |
| Gate 1 | <30 s | Presenter approval |
| 3: Bronze ingestion (16 API calls) | ~1–2 min | Agent (terminal script) |
| Gate 2 | <30 s | Presenter approval |
| 4: SDP pipeline (4 MVs, serverless) | ~1.5–2 min | Agent (terminal) |
| Gate 3 | <30 s | Presenter approval |
| 5: AI/BI Dashboard (3 queries + build) | ~2 min | Agent (MCP dashboard) |
| Gate 4 | <30 s | Presenter approval |
| 6: Genie Space + smoke-test | ~1.5 min | Agent (MCP Genie) |
| Gate 5 | <30 s | Presenter approval |
| 7: Live Q&A | ~1–2 min | Presenter + Agent |
| **Total** | **~10–12 min** | |

---

## Pre-Staged Files Reference

These files are committed to the repo and must exist before running this prompt:

| File | Purpose |
|------|---------|
| `cop_demo/data/cities.json` | 8 Norwegian cities with hardcoded lat/lon (no geocoding) |
| `cop_demo/scripts/ingest_bronze.py` | Bronze API ingestion (databricks-sdk + urllib.request) |
| `cop_demo/pipeline/src/norway_weather_etl/silver_weather_daily.py` | SDP MV: Bronze → Silver weather |
| `cop_demo/pipeline/src/norway_weather_etl/silver_air_hourly.py` | SDP MV: Bronze → Silver air quality |
| `cop_demo/pipeline/src/norway_weather_etl/gold_sunshine_14d_rank.py` | SDP MV: Silver → Gold sunshine rank |
| `cop_demo/pipeline/src/norway_weather_etl/gold_clean_air_rank.py` | SDP MV: Silver → Gold air rank |
| `cop_demo/pipeline/resources/norway_weather_etl.pipeline.yml` | SDP pipeline resource (serverless) |
| `cop_demo/notebooks/00_demo_driver.py` | Validation-only notebook (counts, spot-checks, reset) |
| `databricks.yml` | Bundle root — includes pipeline YAML via glob |

---

## Post-Demo Cleanup (Optional)

To reset Bronze only (Silver/Gold rebuild automatically on next pipeline run):

```sql
TRUNCATE TABLE cop_weather_demo.bronze.openmeteo_weather_raw;
TRUNCATE TABLE cop_weather_demo.bronze.openmeteo_air_raw;
```

To drop everything and start from scratch:

```sql
DROP CATALOG IF EXISTS cop_weather_demo CASCADE;
```

Also delete the pipeline resource (to avoid stale state):

```bash
databricks bundle destroy --target dev --profile dbx_free
```
