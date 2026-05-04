"""
Silver: air_hourly - one row per city per forecast hour (latest run_ts).
Source: cop_weather_demo.bronze.openmeteo_air_raw
Output: cop_weather_demo.silver.air_hourly
Columns: run_ts, city, ts TIMESTAMP, pm2_5 DOUBLE, european_aqi DOUBLE
Note: horizon = 7 days (168 hours) - Open-Meteo Air Quality API max.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, DoubleType, StringType, StructField, StructType

CATALOG = "cop_weather_demo"
BRONZE = f"{CATALOG}.bronze.openmeteo_air_raw"

_SCHEMA = StructType([
    StructField(
        "hourly",
        StructType([
            StructField("time", ArrayType(StringType()), True),
            StructField("pm2_5", ArrayType(DoubleType()), True),
            StructField("european_aqi", ArrayType(DoubleType()), True),
        ]),
        True,
    )
])


@dp.materialized_view(
    name=f"{CATALOG}.silver.air_hourly",
    comment="Hourly air quality per city, latest run_ts only. Source: Open-Meteo /v1/air-quality, 7-day horizon (API max).",
)
def silver_air_hourly():
    raw = spark.sql(
        f"""
        SELECT run_ts, city, payload_json FROM {BRONZE}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {BRONZE})
    """
    )
    parsed = (
        raw.withColumn("p", F.from_json(F.col("payload_json"), _SCHEMA))
        .withColumn("time_arr", F.col("p.hourly.time"))
        .withColumn("pm25_arr", F.col("p.hourly.pm2_5"))
        .withColumn("aqi_arr", F.col("p.hourly.european_aqi"))
    )
    exploded = parsed.select(
        F.col("run_ts"),
        F.col("city"),
        F.col("pm25_arr"),
        F.col("aqi_arr"),
        F.posexplode("time_arr").alias("pos", "ts_str"),
    )
    return exploded.withColumn(
        "pm2_5", F.col("pm25_arr").getItem(F.col("pos"))
    ).withColumn(
        "european_aqi", F.col("aqi_arr").getItem(F.col("pos"))
    ).select(
        F.col("run_ts"),
        F.col("city"),
        F.to_timestamp(F.col("ts_str"), "yyyy-MM-dd'T'HH:mm").alias("ts"),
        F.col("pm2_5"),
        F.col("european_aqi"),
    )