# Football Data Warehouse Pipeline

An end-to-end data engineering pipeline that extracts European football league standings, validates and transforms the data, augments it with Faker-generated synthetic records, loads it into a normalized OLTP database, and builds a star-schema warehouse for analytics — all orchestrated with Airflow.

## Architecture

The pipeline consists of five stages:

1. **Extract**
   - Reads raw standings CSV (`;`-delimited)
   - Validates expected columns exist
   - Logs row counts to `logs/extract.log`

2. **Transform**
   - Splits messy `"Name - N"` scorer fields into name + goals
   - Maps country codes to league names
   - Generates ~14,000 additional synthetic team-season rows with Faker (seeded for reproducibility)
   - Combines real + synthetic data, flagged by `source`

3. **Quality**
   - 5 automated checks: nulls, ranges, consistency (W+D+L=MP, GD=GF-GA), uniqueness, referential integrity
   - Gates the load — bad data never reaches the database

4. **Load (OLTP)**
   - Idempotent upserts into a normalized PostgreSQL schema
   - Get-or-create pattern for leagues, teams, seasons, players — safe to re-run

5. **Warehouse Load**
   - Separate ETL step reads from OLTP, populates a star schema
   - Fact table + 4 dimensions (team, season, player, date)

## Data Flow
              ┌───────────────┐
              │   Raw CSV     │
              │ (standings)   │
              └───────┬───────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│ EXTRACT │
│ Reads CSV → validates columns → logs row count │
└────────────────────────┬────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────┐
│ TRANSFORM │
│ ┌───────────┐ ┌───────────────┐ ┌──────────────┐ │
│ │ Clean real │ │ League lookup │ │ Faker │ │
│ │ fields │ │ (country→lg) │ │ synthetic data│ │
│ └─────┬──────┘ └───────┬───────┘ └──────┬───────┘ │
│ └──────────────────┼──────────────────┘ │
│ Combined dataset │
└────────────────────────┬────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────┐
│ QUALITY GATE │
│ Null · Range · Consistency · Uniqueness · Referential │
│ → fail = abort load, no bad data persisted │
└────────────────────────┬────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────┐
│ LOAD (OLTP) │
│ leagues → teams → seasons → players → team_season_stats │
│ Idempotent upserts (safe to re-run) │
└────────────────────────┬────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────┐
│ WAREHOUSE LOAD │
│ dim_team · dim_season · dim_player · dim_date │
│ → fact_team_season_performance (star schema) │
└──────────────────────────────────────────────────────────┘
## Orchestration

Airflow DAG (`football_etl`) runs the pipeline daily with automatic retries (3 attempts, 5-minute delay):
Scheduler (@daily)
│
▼
Task: extract
│
▼
Task: transform_quality_load (transform → quality → OLTP load)
│
▼
Task: warehouse_load (populates star schema)
## Tech Stack
- PostgreSQL (Docker) — OLTP + warehouse databases
- Python, pandas, psycopg2 — pipeline logic
- Faker — synthetic data generation (seeded, reproducible)
- Apache Airflow — orchestration, scheduling, retries
- DBeaver — database inspection and querying
- Docker Compose — multi-service local environment

## Project Structure
- `pipeline/` — extract, transform, quality, load, warehouse_load, generate_synthetic
- `sql/migrations/` — numbered SQL migration files (OLTP schema)
- `sql/` — warehouse schema DDL
- `dags/` — Airflow DAG definition
- `tests/` — pytest test suite for extract/transform/quality
- `docs/` — ERD diagram
- `data/raw/` — source CSV
- `logs/` — run logs (extract, transform, quality, load, warehouse_load)
- `docker-compose.yml` — Postgres + Airflow services
- `Dockerfile.airflow` — custom Airflow image with pipeline dependencies

## Entity Relationship Diagram
![ERD](docs/erd.png)

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your own values
3. Start the stack:
```sh
   docker compose up -d
```
4. Run migrations to build the OLTP schema:
```sh
   python pipeline/run_migrations.py
```
5. Run the warehouse schema SQL (`sql/warehouse_schema.sql`) in DBeaver against the `football_dwh` database
6. Run the pipeline manually, or trigger it from the Airflow UI:
```sh
   python -m pipeline.load
   python -m pipeline.warehouse_load
```
7. Access Airflow at http://localhost:8081 (user: admin, password: admin)

## Data Quality Checks
- Null check on required fields
- Range check (e.g. points-per-match ≤ 3.0, matches played ≤ 38)
- Consistency check (W+D+L = MP, GD = GF-GA)
- Uniqueness check (no duplicate team/date snapshots)
- Referential check (league names match the known set of 5 leagues)

## Requirements
- Python 3.11+
- Docker Desktop (Windows/Mac/Linux)
- DBeaver Community Edition

## Notes
- Dataset combines 98 real rows (2022-23 European league standings) with ~14,000 Faker-generated synthetic rows spanning 5 seasons, seeded for reproducibility across runs.
- Pipeline is fully idempotent — safe to re-run without creating duplicate rows.
- Custom Airflow image (`Dockerfile.airflow`) bakes in `pandas`, `psycopg2-binary`, `python-dotenv`, and `faker` so all Airflow containers (init, scheduler, webserver) have consistent dependencies.

## Future Improvements
- Add incremental/watermark-based loading instead of full reload each run
- Add data lineage tracking
- Build a small BI dashboard on top of the warehouse (e.g. Metabase or Superset)
- Add CI (GitHub Actions) to run pytest automatically on push