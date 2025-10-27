from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pathlib import Path
import sys

# src 경로 추가
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from tasks.update_model import run as update_model_run

default_args = {
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
}

with DAG(
    dag_id="update_model_daily",
    description="매일 로그 반영 업데이트",
    schedule_interval=None,
    default_args=default_args,
    tags=["lightfm", "update"],
) as dag:

    update_task = PythonOperator(
        task_id="update_model",
        python_callable=update_model_run,
    )
