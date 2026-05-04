"""
Silver: weather_daily
=====================
Materialized View — one row per city per forecast day for the latest run_ts.

Source : cop_weather_demo.bronze.openmeteo_weather_raw
Output : cop_weather_demo.silver.weather_daily

Columns:
  run_ts                   TIMESTAMP  – demo snapshot identifier
  city                     STRING
  date                     DATE       – forecast date (Europe/Oslo)
  sunshine_duration_seconds DOUBLE   – raw seconds from Open-Meteo daily.sunshine_duration
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType, DoubleType, StringType, StructField, StructType,
)

CATALOG = "cop_weather_demo"
BRONZE  = f"{CATALOG}.bronze.openmeteo_weather_raw"

_PAYLOAD_SCHEMA = StructType([
    StructField("daily", StructType([
        StructField("time",               ArrayType(StringType()), True),
        StructField("sunshine_duration",  ArrayType(DoubleType()), True),
    ]), True),
])


@dp.materialized_view(
    name=f"{CATALOG}.silver.weather_daily",
    comment=(
        "Normalized daily weather: one row per city per forecast day. "
        "Filtered to latest run_ts. Source: Open-Meteo /v1/forecast "
        "(daily=sunshine_duration, forecast_days=14, timezone=Europe/Oslo)."
    ),
)
def silver_weather_daily():
    # Read only the latest Bronze snapshot
    raw = spark.sql(f"""
        SELECT run_ts, city, payload_json
        FROM   {BRONZE}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {BRONZE})
    """)

    parsed = (
        raw
        .withColumn("p",       F.from_json(F.col("payload_json"), _PAYLOAD_SCHEMA))
        .withColumn("time_arr", F.col("p.daily.time"))
        .withColumn("sun_arr",  F.col("p.daily.sunshine_duration"))
    )

    # posexplode time array → (pos, date_str); index into sun_arr with pos
    exploded = parsed.select(
        F.col("run_ts"),
        F.col("city"),
        F.col("sun_arr"),
        F.posexplode("time_arr").alias("pos", "date_str"),
    )

    return (
        exploded
        .withColumn("sunshine_duration_seconds", F.col("sun_arr").getItem(F.col("pos")))
        .select(
            F.col("run_ts"),
            F.col("city"),
            F.col("date_str").cast("date").alias("date"),
            F.col("sunshine_duration_seconds"),
        )
    )
