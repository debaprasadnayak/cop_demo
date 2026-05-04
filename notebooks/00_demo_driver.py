# Databricks notebook source
# Norway Weather Demo – Validation Notebook
# ==========================================
# PURPOSE : Validation and cleanup ONLY. No build steps here.
# All build (catalog, schemas, tables, pipeline, dashboard, Genie)
# is orchestrated by the agent-mode prompt:
#   cop_demo/project-docs/plan-norwayWeatherLiveDemo.prompt.md
#
# Run individual cells to spot-check each layer after each GO/NO-GO gate.

# COMMAND ----------

# Configuration – change CATALOG if you renamed it
CATALOG = "cop_weather_demo"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gate 1 – Bronze Layer Check
# MAGIC Run after Step 3 (Bronze ingestion) to verify counts and payload quality.

# COMMAND ----------

# Bronze row counts and latest run_ts
display(spark.sql(f"""
  SELECT
    source,
    COUNT(*)           AS row_count,
    MAX(run_ts)        AS latest_run_ts,
    MIN(run_ts)        AS earliest_run_ts
  FROM (
    SELECT 'weather'     AS source, run_ts FROM {CATALOG}.bronze.openmeteo_weather_raw
    UNION ALL
    SELECT 'air_quality' AS source, run_ts FROM {CATALOG}.bronze.openmeteo_air_raw
  )
  GROUP BY source
  ORDER BY source
"""))
# Expected: weather=8 rows, air_quality=8 rows

# COMMAND ----------

# Bronze: spot-check weather payload (first/last date per city)
display(spark.sql(f"""
  SELECT
    city,
    run_ts,
    get_json_object(payload_json, '$.daily.time[0]')   AS forecast_start,
    get_json_object(payload_json, '$.daily.time[13]')  AS forecast_end_14d,
    length(payload_json)                               AS payload_bytes
  FROM {CATALOG}.bronze.openmeteo_weather_raw
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.bronze.openmeteo_weather_raw)
  ORDER BY city
"""))

# COMMAND ----------

# Bronze: spot-check air quality payload (first/last hour per city)
display(spark.sql(f"""
  SELECT
    city,
    run_ts,
    get_json_object(payload_json, '$.hourly.time[0]')    AS forecast_start,
    get_json_object(payload_json, '$.hourly.time[167]')  AS forecast_end_7d,
    length(payload_json)                                 AS payload_bytes
  FROM {CATALOG}.bronze.openmeteo_air_raw
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.bronze.openmeteo_air_raw)
  ORDER BY city
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gate 2 – Silver Layer Check
# MAGIC Run after the SDP pipeline completes to verify Silver row counts.

# COMMAND ----------

# Silver row counts (expected: weather_daily=112 = 8×14, air_hourly≈1344 = 8×168)
display(spark.sql(f"""
  SELECT 'weather_daily' AS table_name, COUNT(*) AS row_count,
         COUNT(DISTINCT city) AS cities, COUNT(DISTINCT date) AS dates
  FROM {CATALOG}.silver.weather_daily
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.silver.weather_daily)
  UNION ALL
  SELECT 'air_hourly', COUNT(*),
         COUNT(DISTINCT city), COUNT(DISTINCT CAST(ts AS DATE))
  FROM {CATALOG}.silver.air_hourly
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.silver.air_hourly)
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gate 3 – Gold Layer Check (Demo Answers)
# MAGIC Run after the SDP pipeline to confirm both demo questions can be answered.

# COMMAND ----------

# Q1: Sunniest city in the next 14 days
display(spark.sql(f"""
  SELECT
    rank,
    city,
    ROUND(sunshine_hours_14d, 1) AS sunshine_hours_14d
  FROM {CATALOG}.gold.sunshine_14d_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.gold.sunshine_14d_rank)
  ORDER BY rank
"""))
# rank=1 = sunniest city

# COMMAND ----------

# Q2: Cleanest air city in the next 7 days
display(spark.sql(f"""
  SELECT
    rank_pm25,
    rank_aqi,
    city,
    ROUND(avg_pm2_5_horizon, 2)        AS avg_pm25_ug_m3,
    ROUND(avg_european_aqi_horizon, 1) AS avg_european_aqi
  FROM {CATALOG}.gold.clean_air_rank
  WHERE run_ts = (SELECT MAX(run_ts) FROM {CATALOG}.gold.clean_air_rank)
  ORDER BY rank_pm25
"""))
# rank_pm25=1 = cleanest air by PM2.5

# COMMAND ----------

# Reference cities (static, loaded once)
display(spark.sql(f"SELECT * FROM {CATALOG}.bronze.ref_cities ORDER BY city"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo Reset (optional)
# MAGIC Uncomment and run **only** to truncate Bronze for a clean re-run.
# MAGIC Silver and Gold auto-rebuild from Bronze via the SDP pipeline.

# COMMAND ----------

# UNCOMMENT TO RESET:
# spark.sql(f"TRUNCATE TABLE {CATALOG}.bronze.openmeteo_weather_raw")
# spark.sql(f"TRUNCATE TABLE {CATALOG}.bronze.openmeteo_air_raw")
# print(f"Bronze tables truncated in {CATALOG}. Ready for fresh ingestion.")
