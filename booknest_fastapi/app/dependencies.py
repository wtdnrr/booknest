# app/dependencies.py
from sqlalchemy.orm import sessionmaker
from app.config import engine
import boto3
from app import config
import redis
from elasticsearch import Elasticsearch
from app import config


# 데이터베이스 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        region_name=config.AWS_REGION,
    )


def get_redis_client():
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True
    )


def get_elasticsearch_client():
    return Elasticsearch(
        config.ELASTICSEARCH_HOST,
        basic_auth=(config.ELASTIC_USERNAME, config.ELASTIC_PASSWORD)
    )