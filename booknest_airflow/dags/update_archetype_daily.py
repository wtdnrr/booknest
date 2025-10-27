# dags/assign_user_archetypes_dag.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# src 경로 추가
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from tasks.update_archetype import assign_user_archetypes

default_args = {
    'owner': 'booknest',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='update_archetypes_daily',
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['archetype', 'users'],
) as dag:

    assign_archetypes = PythonOperator(
        task_id='assign_archetypes_task',
        python_callable=assign_user_archetypes,
    )