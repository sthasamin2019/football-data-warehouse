
import sys
sys.path.insert(0, '/opt/airflow')

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


def run_extract():
    from pipeline.extract import extract
    df = extract()
    print(f"Extracted {len(df)} rows")


def run_transform_and_quality_and_load():
    from pipeline.extract import extract
    from pipeline.transform import transform
    from pipeline.quality import run_quality_checks
    from pipeline.load import load

    raw = extract()
    result = transform(raw)
    checks = run_quality_checks(result["team_season_stats"])
    failed = [c for c in checks if not c.passed]
    if failed:
        raise ValueError(f"Quality checks failed: {failed}")
    load(result["team_season_stats"], result.get("top_scorers"), result.get("goalkeepers"))


def run_warehouse_load():
    from pipeline.warehouse_load import run_warehouse_etl
    run_warehouse_etl()


default_args = {
    "owner": "airflow",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="football_etl",
    default_args=default_args,
    description="Extract, transform, validate, and load football stats into OLTP and warehouse",
    start_date=datetime(2024, 1, 1),
    schedule="*/2 * * * *",
    catchup=False,
    tags=["football", "etl"],
) as dag:

    extract_task = PythonOperator(
        task_id="extract",
        python_callable=run_extract,
    )

    transform_quality_load_task = PythonOperator(
        task_id="transform_quality_load",
        python_callable=run_transform_and_quality_and_load,
    )

    warehouse_load_task = PythonOperator(
        task_id="warehouse_load",
        python_callable=run_warehouse_load,
    )

    extract_task >> transform_quality_load_task >> warehouse_load_task
