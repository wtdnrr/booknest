import boto3
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_s3_client():
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION")
        )
        print("[s3_utils] S3 연결 성공")
        return s3
    except Exception as e:
        print(f"[s3_utils] S3 연결 실패: {e}")
        raise


def upload_to_s3(file_path, bucket_name, s3_key):
    try:
        s3 = get_s3_client()
        s3.upload_file(file_path, bucket_name, s3_key)
        print(f"[s3_utils] S3 업로드 완료 → s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"[s3_utils] S3 업로드 실패: {e}")
        raise


def download_csv_from_s3(bucket_name, s3_key, local_path):
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3 = get_s3_client()
        s3.download_file(bucket_name, s3_key, local_path)
        print(f"[s3_utils] 다운로드 완료: {s3_key} → {local_path}")
        return local_path
    except Exception as e:
        print(f"[s3_utils] CSV 다운로드 실패: {e}")
        raise


def load_csv_from_s3(bucket_name, s3_key, local_path):
    try:
        path = download_csv_from_s3(bucket_name, s3_key, local_path)
        df = pd.read_csv(path)
        print(f"[s3_utils] CSV 로드 완료: {len(df)} rows from {path}")
        return df
    except Exception as e:
        print(f"[s3_utils] CSV 로드 실패: {e}")
        raise


def download_and_load_pickle_from_s3(bucket_name, s3_key, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        s3 = get_s3_client()
        s3.download_file(bucket_name, s3_key, local_path)
        print(f"[s3_utils] 다운로드 완료: {s3_key} → {local_path}")
        import pickle
        with open(local_path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[s3_utils] 다운로드 실패: {e}")
        raise
