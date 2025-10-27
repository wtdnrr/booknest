from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pathlib import Path
import sys

# src 경로 추가
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

# 각 task import
from tasks.load_data import run as load_data_run
from tasks.build_matrix import run as build_matrix_run
from tasks.train_model import run as train_model_run

default_args = {
    "owner": "booknest",
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
}

with DAG(
    dag_id="train_model_pipeline",
    description="DB 로딩 → 행렬 생성 → 모델 학습까지 전체 파이프라인",
    schedule_interval=None,  # 수동 실행 (@daily로 바꾸면 자동 실행)
    default_args=default_args,
    tags=["recommender", "lightfm", "full_pipeline"],
) as dag:

    task_load_data = PythonOperator(
        task_id="load_data",
        python_callable=load_data_run,
    )

    task_build_matrix = PythonOperator(
        task_id="build_matrix",
        python_callable=build_matrix_run,
    )

    task_train_model = PythonOperator(
        task_id="train_model",
        python_callable=train_model_run,
    )

    # 실행 순서 지정
    task_load_data >> task_build_matrix >> task_train_model
