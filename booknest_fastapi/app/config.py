# app/config.py
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv


load_dotenv()  # 로컬에서만 유효.

# MariaDB 접속 URL 작성 (mariadbconnector 사용 예)
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_URL = f"mariadb+mariadbconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 연결 풀 설정 (예: pool_size=20, max_overflow=0)
engine = create_engine(DB_URL, pool_size=20, max_overflow=0)


# S3 설정
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.environ.get("AWS_REGION")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")


# Redis 설정
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))


# ElasticSearch 설정
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST")
ELASTIC_USERNAME = os.getenv("ELASTIC_USERNAME")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")