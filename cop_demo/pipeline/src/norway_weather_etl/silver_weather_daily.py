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
