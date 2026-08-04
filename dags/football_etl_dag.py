# =====================================================================
# Airflow DAG: football_etl
#
# Orchestrates the full data pipeline end-to-end:
#   1. Extract  -> read raw CSV
#   2. Transform + Quality + Load -> clean data, validate, write to OLTP
#   3. Warehouse Load -> populate the star-schema warehouse
#
# Runs automatically on a schedule with retries if a step fails.
# =====================================================================

import sys
# Makes the 'pipeline' package (extract, transform, etc.) importable
# from inside the Airflow container
sys.path.insert(0, '/opt/airflow')

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


def run_extract():
    """Task 1: Read the raw CSV and confirm how many rows were found."""
    from pipeline.extract import extract
    df = extract()
    print(f"Extracted {len(df)} rows")


def run_transform_and_quality_and_load():
    """
    Task 2: Clean and reshape the data, run 5 automated quality checks,
    and load the result into the OLTP database.

    These three steps are combined into a single Airflow task because
    they share one in-memory dataset (a pandas DataFrame) -- splitting
    them into separate tasks would mean passing large DataFrames between
    tasks, which Airflow isn't designed for.

    If any quality check fails, the load is aborted -- bad data never
    reaches the database.
    """
    from pipeline.extract import extract
    from pipeline.transform import transform
    from pipeline.quality import run_quality_checks
    from pipeline.load import load

    raw = extract()
    result = transform(raw)

    checks = run_quality_checks(result["team_season_stats"])
    failed = [c for c in checks if not c.passed]
    if failed:
        # Raising an error here marks the task as failed in Airflow,
        # which triggers the retry logic defined in default_args below
        raise ValueError(f"Quality checks failed: {failed}")

    load(result["team_season_stats"], result.get("top_scorers"), result.get("goalkeepers"))


def run_warehouse_load():
    """
    Task 3: Read the newly loaded OLTP data and populate the star-schema
    warehouse (fact table + dimension tables) for analytics.
    """
    from pipeline.warehouse_load import run_warehouse_etl
    run_warehouse_etl()


# Settings applied to every task in this DAG
default_args = {
    "owner": "airflow",
    "retries": 3,              # retry a failed task up to 3 times
    "retry_delay": timedelta(minutes=5),  # wait 5 minutes between retries
}

with DAG(
    dag_id="football_etl",
    default_args=default_args,
    description="Extract, transform, validate, and load football stats into OLTP and warehouse",
    start_date=datetime(2024, 1, 1),
    schedule="*/2 * * * *",   # NOTE: set to every 2 minutes for testing;
                                # switch to "@daily" before final submission
    catchup=False,              # don't backfill runs for past dates
    tags=["football", "etl"],
) as dag:

    # Task 1: extract raw data
    extract_task = PythonOperator(
        task_id="extract",
        python_callable=run_extract,
    )

    # Task 2: transform, validate, and load into OLTP
    transform_quality_load_task = PythonOperator(
        task_id="transform_quality_load",
        python_callable=run_transform_and_quality_and_load,
    )

    # Task 3: populate the warehouse from OLTP
    warehouse_load_task = PythonOperator(
        task_id="warehouse_load",
        python_callable=run_warehouse_load,
    )

    # Defines execution order: each task only runs after the previous
    # one succeeds -- this is what creates the pipeline sequence in the
    # Airflow UI's graph view
    extract_task >> transform_quality_load_task >> warehouse_load_task