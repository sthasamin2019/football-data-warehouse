# Football Data Warehouse Pipeline

An end-to-end data engineering pipeline that extracts European football league standings, transforms and validates the data, augments it with Faker-generated synthetic records, loads it into a normalized OLTP database, and builds a star-schema warehouse for analytics — orchestrated with Airflow and visualized in Metabase.

## Architecture

The pipeline consists of five stages:

1. **Extract**
   - Reads the raw standings CSV
   - Validates expected columns
   - Logs row counts

2. **Transform**
   - Cleans messy scorer/goalkeeper fields
   - Maps country codes to league names
   - Generates ~14,000 synthetic rows with Faker (seeded, reproducible)

3. **Quality Gate**
   - 5 automated checks: null, range, consistency, uniqueness, referential integrity
   - A failed check aborts the load — bad data never reaches the database

4. **Load (OLTP)**
   - Idempotent upserts into a normalized PostgreSQL schema
   - Safe to re-run without creating duplicates

5. **Warehouse Load**
   - Reads from OLTP, populates a star schema
   - One fact table, four dimensions (team, season, player, date)

## Data Flow

\`\`\`
Raw CSV -> Extract -> Transform -> Quality Gate -> Load (OLTP) -> Warehouse Load
\`\`\`

## Orchestration & Visualization
- **Airflow**: orchestrates the full pipeline daily, with automatic retries (DAG: \`football_etl\`)
- **Metabase**: dashboards built on top of the warehouse for analytics
- **DBeaver**: used for inspecting and querying both databases

## Project Structure
- \`pipeline/\` - extract, transform, quality, load, warehouse_load, generate_synthetic
- \`sql/migrations/\` - numbered SQL migration files (OLTP schema)
- \`sql/\` - warehouse schema DDL
- \`dags/\` - Airflow DAG definition
- \`tests/\` - pytest test suite
- \`data/raw/\` - source CSV
- \`logs/\` - run logs
- \`docker-compose.yml\` - Postgres, Airflow, and Metabase services
- \`Dockerfile.airflow\` - custom Airflow image with pipeline dependencies

## Setup
1. Clone the repo
2. Copy \`.env.example\` to \`.env\` and fill in your own values
3. Start the stack:
   \`\`\`sh
   docker compose up -d
   \`\`\`
4. Run migrations to build the OLTP schema:
   \`\`\`sh
   python pipeline/run_migrations.py
   \`\`\`
5. Run the warehouse schema SQL (\`sql/warehouse_schema.sql\`) against the \`football_dwh\` database
6. Load the data:
   \`\`\`sh
   python -m pipeline.load
   python -m pipeline.warehouse_load
   \`\`\`
7. Access Airflow at http://localhost:8081 and Metabase at http://localhost:3000

## Data Quality Checks
- Null check on required fields
- Range check (e.g. points-per-match <= 3.0, matches played <= 38)
- Consistency check (W+D+L = MP, GD = GF-GA)
- Uniqueness check (no duplicate team/date snapshots)
- Referential check (league names match the known set)

## Requirements
- Python 3.11+
- Docker and Docker Compose
- DBeaver (for database inspection)

## Demo
[VIDEO LINK GOES HERE]
