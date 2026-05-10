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
