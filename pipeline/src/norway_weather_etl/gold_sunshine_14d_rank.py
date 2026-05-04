"""
Gold: sunshine_14d_rank
=======================
Materialized View — 14-day total sunshine hours per city, ranked descending.

Source : cop_weather_demo.silver.weather_daily
Output : cop_weather_demo.gold.sunshine_14d_rank

Columns:
  run_ts              TIMESTAMP – demo snapshot identifier
  city                STRING
  sunshine_hours_14d  DOUBLE    – SUM(sunshine_duration_seconds)/3600 across 14 days
  rank                INT       – 1 = sunniest city

Metric definition:
  "Sunniest city" = city with rank = 1
  sunshine_hours_14d = SUM(daily.sunshine_duration_seconds) / 3600.0
  Ranked DESCENDING: higher hours = lower rank number (1 = best).
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = "cop_weather_demo"
SILVER  = f"{CATALOG}.silver.weather_daily"


@dp.materialized_view(
    name=f"{CATALOG}.gold.sunshine_14d_rank",
    comment=(
        "14-day sunshine ranking for 8 Norwegian cities. "
        "rank=1 is the sunniest. sunshine_hours_14d = SUM(seconds)/3600. "
        "Always filter to MAX(run_ts) for current demo snapshot."
    ),
)
def gold_sunshine_14d_rank():
    silver = spark.sql(f"""
        SELECT run_ts, city, sunshine_duration_seconds
        FROM   {SILVER}
        WHERE  run_ts = (SELECT MAX(run_ts) FROM {SILVER})
    """)

    window = Window.partitionBy("run_ts").orderBy(F.col("sunshine_hours_14d").desc())

    return (
        silver
        .groupBy("run_ts", "city")
        .agg(
            (F.sum("sunshine_duration_seconds") / F.lit(3600.0))
            .alias("sunshine_hours_14d")
        )
        .withColumn("rank", F.rank().over(window))
    )
