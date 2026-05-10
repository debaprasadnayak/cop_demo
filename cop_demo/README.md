# Norway Weather Demo

A **zero-to-live demonstration** of a complete data pipeline on Databricks. This demo ingests real-time weather and air quality data for 8 Norwegian cities, processes it through a medallion architecture (Bronze → Silver → Gold), and publishes interactive dashboards and AI-powered analytics.

**Key Features:**
- 🌍 Real-world data: Open-Meteo weather & air quality APIs
- 📊 Medallion architecture: Bronze (raw) → Silver (refined) → Gold (analytics-ready)
- ⚡ Serverless compute: No clusters—everything uses Databricks Serverless SQL & DLT pipelines
- 🎯 Multi-layer analytics: Rankings, aggregations, and time-series forecasting
- 📈 Interactive dashboards: Databricks AI/BI for visualization
- 🤖 Natural language queries: Genie Space for exploratory analytics

---

## Quick Start

### Prerequisites

1. **Databricks Workspace** (free tier compatible)
   - Access to a Databricks workspace
   - Databricks CLI installed: `brew install databricks` (macOS) or follow [docs](https://docs.databricks.com/en/dev-tools/cli/index.html)

2. **SQL Warehouse**
   - At least one SQL warehouse (size: 2X-Small or larger)
   - Note the warehouse ID

3. **Python Environment** (for bronze data ingestion)
   - Python 3.8+
   - Install dependencies:
     ```bash
     pip install databricks-sdk
     ```

### Configuration

1. **Authenticate with Databricks CLI:**
   ```bash
   databricks auth login --profile YOUR_PROFILE
   ```
   Replace `YOUR_PROFILE` with a friendly name (e.g., `my-databricks`).

2. **Update configuration files** with your profile and warehouse ID:

   Edit [`cop_demo/scripts/ingest_bronze.py`](cop_demo/scripts/ingest_bronze.py#L14-L15):
   ```python
   PROFILE       = "YOUR_PROFILE"        # Your CLI profile name
   WAREHOUSE_ID  = "YOUR_WAREHOUSE_ID"   # Your SQL warehouse ID
   ```

3. **Update bundle configuration** in [`databricks.yml`](databricks.yml#L18):
   ```yaml
   targets:
     dev:
       workspace:
         host: https://dbc-YOUR_INSTANCE_ID.cloud.databricks.com
   ```
   Find your instance ID in your Databricks workspace URL: `https://dbc-**a1b2c3d4-5678**.cloud.databricks.com`

---

## Architecture Overview

### Data Flow

```
┌─────────────────────┐
│   API Ingestion     │  (Open-Meteo)
│  (Bronze Layer)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Spark Declarative  │
│     Pipeline (DLT)  │  ← Transformation
│  (Silver + Gold)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Gold Analytics    │
│  - Dashboards       │
│  - Genie Spaces     │
└─────────────────────┘
```

### Data Model

| Layer | Table | Rows/run | Purpose |
|-------|-------|----------|---------|
| **Bronze** | `openmeteo_weather_raw` | 8 | Raw API snapshots—weather forecasts |
| **Bronze** | `openmeteo_air_raw` | 8 | Raw API snapshots—air quality |
| **Bronze** | `ref_cities` | 8 | Static reference—city coordinates |
| **Silver** | `weather_daily` | 112 | Expanded daily records (8 cities × 14 days) |
| **Silver** | `air_hourly` | ~1,344 | Expanded hourly records (8 cities × 168 hrs) |
| **Gold** | `sunshine_14d_rank` | 8 | Ranking—sunniest cities (next 14 days) |
| **Gold** | `clean_air_rank` | 8 | Ranking—cleanest air (next 7 days) |

### Analytics Questions

1. **Q1: Which city has the most sunshine over the next 14 days?**
   - Source: `gold.sunshine_14d_rank`
   - Metric: Total sunshine hours (descending)

2. **Q2: Which city has the cleanest air?**
   - Source: `gold.clean_air_rank`
   - Metrics: Average PM2.5 & European AQI (7-day horizon)

---

## Project Structure

```
cop_demo/
├── README.md                           # This file
├── LICENSE                             # Project license
├── data/
│   └── cities.json                    # Reference data (8 Norwegian cities)
├── scripts/
│   └── ingest_bronze.py               # Bronze data ingestion script
├── pipeline/
│   ├── resources/
│   │   └── norway_weather_etl.pipeline.yml   # DLT pipeline definition
│   └── src/
│       └── norway_weather_etl/
│           ├── silver_weather_daily.py       # Silver transformations
│           ├── silver_air_hourly.py          # Silver transformations
│           ├── gold_sunshine_14d_rank.py     # Gold rankings
│           └── gold_clean_air_rank.py        # Gold rankings
├── notebooks/
│   └── 00_demo_driver.py               # Validation & cleanup notebook
├── project-docs/
│   ├── plan-norwayWeatherLiveDemo.prompt.md           # Full demo workflow
│   └── norwayWeatherLiveDemo.highlevel-checklist.md  # Execution status
└── project-tasks/
    └── norwayWeatherLiveDemo.execution-plan.md       # Step-by-step guide
```

---

## Running the Demo

### Phase 1: Infrastructure Setup

1. **Validate the bundle:**
   ```bash
   databricks bundle validate --profile YOUR_PROFILE
   ```

2. **Deploy to your workspace:**
   ```bash
   databricks bundle deploy --target dev --profile YOUR_PROFILE
   ```
   This creates the Spark Declarative Pipeline in your workspace.

### Phase 2: Bronze Data Ingestion

Run the ingestion script to fetch live weather & air quality data:

```bash
python cop_demo/scripts/ingest_bronze.py
```

**Output:**
```
Norway Weather Demo – Bronze Ingestion
  Loaded 8 cities
  Warehouse ID: YOUR_WAREHOUSE_ID
  run_ts: 2026-05-10 14:30:00

Ingesting weather forecast (sunshine_duration, 14 days)...
  ✓ Bergen
  ✓ Oslo
  ✓ Trondheim
  ... (5 more cities)

Ingesting air quality forecast (pm2_5 + european_aqi, 7 days)...
  ... (8 cities)

Bronze ingestion complete.
  cop_weather_demo.bronze.openmeteo_weather_raw → 8 rows
  cop_weather_demo.bronze.openmeteo_air_raw     → 8 rows
```

### Phase 3: Pipeline Execution

The DLT pipeline automatically transforms Bronze → Silver → Gold when triggered.

**Option A: Trigger via CLI**
```bash
databricks pipelines start-update $(databricks pipelines list --profile YOUR_PROFILE \
  | grep norway_weather_etl | cut -d' ' -f1)
```

**Option B: Trigger via Databricks workspace UI**
- Navigate to **Workflows** → **Lakeflow** → `norway_weather_etl`
- Click **Run now**

### Phase 4: Validate Results

Open the included validation notebook in your workspace:

1. Navigate to **Workspace** → **Notebooks** → `00_demo_driver.py`
2. Run each gate cell individually to verify:
   - Gate 1: Bronze row counts ✓
   - Gate 2: Silver row counts ✓
   - Gate 3a: Sunniest city ranking ✓
   - Gate 3b: Cleanest air ranking ✓

---

## API Data Sources

### Open-Meteo Weather Forecast
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Horizon:** 14 days
- **Metric:** `sunshine_duration_seconds`

### Open-Meteo Air Quality Forecast
- **Endpoint:** `https://air-quality-api.open-meteo.com/v1/air-quality`
- **Horizon:** 7 days (API maximum—CAMS European + Global blend)
- **Metrics:** `pm2_5`, `european_aqi`

> ℹ️ **Note:** Both APIs are free and require no authentication. Data is updated every 4–6 hours.

---

## Cleanup & Reset

### Option 1: Reset Bronze Only
Silver & Gold rebuild automatically on the next pipeline run:

```sql
-- In Databricks SQL warehouse
TRUNCATE TABLE cop_weather_demo.bronze.openmeteo_weather_raw;
TRUNCATE TABLE cop_weather_demo.bronze.openmeteo_air_raw;
```

Then re-run the ingestion script and pipeline.

### Option 2: Full Teardown

Delete the entire catalog and all objects:

```sql
DROP CATALOG IF EXISTS cop_weather_demo CASCADE;
```

Or via Databricks CLI:
```bash
databricks bundle destroy --target dev --profile YOUR_PROFILE
```

---

## Troubleshooting

### Issue: "Profile not found"
**Error:** `databricks.sdk.core.DatabricksError: No credentials found in ~/.databrickscfg`

**Solution:**
1. Run `databricks auth login --profile YOUR_PROFILE`
2. Verify `~/.databrickscfg` contains your profile
3. Re-check `PROFILE` variable in `ingest_bronze.py`

### Issue: Warehouse not found
**Error:** `databricks.sdk.service.sql.InvalidParameterValue: Invalid warehouse_id`

**Solution:**
1. List available warehouses:
   ```bash
   databricks sql warehouses list --profile YOUR_PROFILE
   ```
2. Copy the correct warehouse ID and update `WAREHOUSE_ID` in `ingest_bronze.py`

### Issue: Pipeline fails with "File not found"
**Error:** `[LIBRARY_FILE_NOT_FOUND] /Workspace/...`

**Solution:**
1. Ensure bundle deployment completed successfully
2. Verify pipeline definition includes all SQL files:
   ```bash
   databricks bundle validate --profile YOUR_PROFILE
   ```
3. Re-deploy if needed:
   ```bash
   databricks bundle deploy --target dev --profile YOUR_PROFILE
   ```

### Issue: Insufficient warehouse capacity
**Error:** `No available resources for query`

**Solution:**
- Scale up the warehouse size in Databricks UI
- Or use the Serverless SQL warehouse (recommended)

---

## Next Steps

### Extend the Demo

1. **Add more cities:** Edit `cop_demo/data/cities.json` with additional coordinates
2. **Custom metrics:** Extend `gold_*.py` files to calculate new rankings
3. **Real-time ingestion:** Integrate with Kafka or Zerobus for streaming data
4. **Scheduled pipeline:** Set up a cron job in Databricks workflows

### Learn More

- [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html)
- [Spark Declarative Pipelines](https://docs.databricks.com/en/lakehouse/laakehouse-io/index.html)
- [Unity Catalog](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
- [Databricks AI/BI](https://docs.databricks.com/en/dashboards/index.html)
- [Genie Spaces](https://docs.databricks.com/en/genie/index.html)

---

## Support & Issues

For issues or questions:

1. Check the **Troubleshooting** section above
2. Review project documentation:
   - [`project-tasks/norwayWeatherLiveDemo.execution-plan.md`](project-tasks/norwayWeatherLiveDemo.execution-plan.md) — Step-by-step guide
   - [`project-docs/plan-norwayWeatherLiveDemo.prompt.md`](project-docs/plan-norwayWeatherLiveDemo.prompt.md) — Full workflow details

3. Enable debug logging in the ingestion script:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

## License

See [`LICENSE`](LICENSE) for details.

---

**Happy exploring!** 🏔️ ⛅ 🌬️