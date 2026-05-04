"""
Gold: clean_air_rank
====================
Materialized View — 7-day average PM2.5 and European AQI per city, dual-ranked.

Source : cop_weather_demo.silver.air_hourly
Output : cop_weather_demo.gold.clean_air_rank

Columns:
  run_ts                   TIMESTAMP – demo snapshot identifier
  city                     STRING
  avg_pm2_5_horizon        DOUBLE    – AVG(pm2_5) across all forecast hours (µg/m³)
  avg_european_aqi_horizon DOUBLE    – AVG(european_aqi) across all forecast hours
  rank_pm25                INT       – 1 = cleanest air by PM2.5 (ascending)
  rank_aqi                 INT       – 1 = cleanest air by European AQI (ascending)

Metric definitions:
  "Cleanest air city (PM2.5)"   = city with rank_pm25 = 1
  "Cleanest air city (AQI)"     = city with rank_aqi  = 1
  rank_pm25 and rank_aqi are INDEPENDENT rankings.
  Horizon = 7 days (Open-Meteo Air Quality API maximum forecast_days).
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = "cop_weather_demo"
SILVER  = f"{CATALOG}.silver.air_hourly"


@dp.materialized_view(
    name=f"{CATALOG}.gold.clean_air_rank",
    comment=(
        "7-day air quality ranking for 8 Norwegian cities. "
        "rank_pm25=1 and rank_aqi=1 are the cities with cleanest air. "
        "rank_pm25 (PM2.5-based) and rank_aqi (European AQI-based) are independent. "
        "Horizon = 7 days (Open-Meteo API max). Filter to MAX(run_ts)."
    ),
)
def gold_clean_air_rank():
    silver = spark.sql(f"""
        SELECT run_ts, city, pm2_5, european_aqi
        FROM   {SILVER}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {SILVER})
    """)

    # Aggregations: lower average = cleaner air → rank ASCENDING
    window_pm25 = Window.partitionBy("run_ts").orderBy(F.col("avg_pm2_5_horizon").asc())
    window_aqi  = Window.partitionBy("run_ts").orderBy(F.col("avg_european_aqi_horizon").asc())

    return (
        silver
        .groupBy("run_ts", "city")
        .agg(
            F.avg("pm2_5").alias("avg_pm2_5_horizon"),
            F.avg("european_aqi").alias("avg_european_aqi_horizon"),
        )
        .withColumn("rank_pm25", F.rank().over(window_pm25))
        .withColumn("rank_aqi",  F.rank().over(window_aqi))
    )
