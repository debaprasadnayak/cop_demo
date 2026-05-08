# Norway Weather Live Demo - Execution Plan

Created: 2026-05-07T18:51:56Z
Source Prompt: cop_demo/project-docs/plan-norwayWeatherLiveDemo.prompt.md

## Scope
Build and demo a full Norway weather intelligence flow on Databricks serverless only:
1. Phase A (Senior Data Engineer): source files, bundle deploy, UC setup, Bronze ingest, SDP pipeline.
2. Phase B (Analytics Reporter): AI/BI dashboard, Genie space, smoke tests, live Q&A.

## Preconditions
- Databricks CLI profile: dbx_free
- SQL warehouse id: 0de9375ba014b54e
- No clusters created or used (serverless only)
- Checklist source of truth:
  cop_demo/project-docs/norwayWeatherLiveDemo.highlevel-checklist.md

## Phase A Steps
1. A0 Auth pre-flight
- Validate `databricks auth profiles` and successful `dbx_free` auth.
- Confirm workspace host matches bundle target.

2. A1 Create source files
- Create or verify:
  - cop_demo/data/cities.json
  - cop_demo/scripts/ingest_bronze.py
  - cop_demo/pipeline/src/norway_weather_etl/silver_weather_daily.py
  - cop_demo/pipeline/src/norway_weather_etl/silver_air_hourly.py
  - cop_demo/pipeline/src/norway_weather_etl/gold_sunshine_14d_rank.py
  - cop_demo/pipeline/src/norway_weather_etl/gold_clean_air_rank.py
  - cop_demo/pipeline/resources/norway_weather_etl.pipeline.yml
  - cop_demo/notebooks/00_demo_driver.py

3. A2 Bundle validate + deploy
- Update databricks.yml include:
  - cop_demo/pipeline/resources/*.pipeline.yml
- Run:
  - `databricks bundle validate --profile dbx_free`
  - `databricks bundle deploy --target dev --profile dbx_free`

4. A3 UC catalog/schemas/tables
- Execute SQL to create:
  - catalog: cop_weather_demo
  - schemas: bronze, silver, gold
  - table: bronze.ref_cities
  - tables: bronze.openmeteo_weather_raw, bronze.openmeteo_air_raw
- Verify via information_schema.

5. Gate 1 (GO/NO-GO)
- Expected:
  - catalog/schemas exist
  - ref_cities = 8 rows
  - both raw Bronze tables = 0 rows (baseline)

6. A4 Bronze ingestion
- Run:
  - `.ai-dev-kit/.venv/bin/python cop_demo/scripts/ingest_bronze.py`
- Verify row counts:
  - weather = 8
  - air_quality = 8

7. Gate 2 (GO/NO-GO)
- Expected:
  - both Bronze tables populated for same latest run_ts

8. A5 SDP pipeline run
- Run:
  - `databricks bundle run norway_weather_etl --profile dbx_free`
- Verify latest run_ts counts:
  - silver.weather_daily = 112
  - silver.air_hourly about 1344
  - gold.sunshine_14d_rank = 8
  - gold.clean_air_rank = 8

9. Gate 3 (GO/NO-GO)
- Capture Q1 and Q2 outputs from Gold ranking tables.

## Phase B Steps
1. B1 Dashboard build + publish
- Validate all 3 dataset SQL queries first.
- Create dashboard:
  - Norway Weather - 14-Day Sunshine & 7-Day Air Quality
- Publish and save URL.

2. Gate 4 (GO/NO-GO)
- Confirm all 3 visuals render with latest snapshot data.

3. B2 Genie space + smoke tests
- Create Genie space: Norway Weather Intelligence
- Register 4 tables and prompt instructions.
- Ask 4 seed questions and verify outputs.

4. Gate 5 (GO/NO-GO)
- Confirm Genie URL, seed questions, and expected Q1/Q3 answers.

5. B3 Live Q&A finale
- Run live audience questions in Genie.
- Record final outputs and close run.

## Run Discipline
- After each step and gate, immediately update checklist status to Done/Failed.
- If failed, add one-line reason in Notes with timestamp.
- At completion, set Run End Time and ensure no executed step remains Pending.
