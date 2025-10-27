# src/utils/db_utils.py
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_engine():
    try:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
        engine = create_engine(url)
        print("[db_utils] DB 연결 성공")
        return engine
    except Exception as e:
        print(f"[db_utils] DB 연결 실패: {e}")
        raise