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
