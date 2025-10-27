import pandas as pd
import os
import pickle
from utils.db_utils import get_db_engine

def load_book_df():
    try:
        engine = get_db_engine()
        query = """
            SELECT B.id AS book_id, A.name AS author,
                   GROUP_CONCAT(DISTINCT C.name) AS category,
                   GROUP_CONCAT(DISTINCT T.name) AS tag
            FROM book B
            LEFT JOIN book_author BA ON B.id = BA.book_id
            LEFT JOIN author A ON BA.author_id = A.id
            LEFT JOIN book_category BC ON B.id = BC.book_id
            LEFT JOIN category C ON BC.category_id = C.id
            LEFT JOIN book_tag BT ON B.id = BT.book_id
            LEFT JOIN tag T ON BT.tag_id = T.id
            GROUP BY B.id;
        """
        print("[load_book_df] 도서 데이터 쿼리 실행 중...")
        df = pd.read_sql(query, engine)
        print(f"[load_book_df] {len(df)}건 로드 완료")
        return df
    except Exception as e:
        print(f"[load_book_df] Error: {e}")
        return pd.DataFrame()

def load_user_df():
    try:
        engine = get_db_engine()
        query = "SELECT id AS user_id FROM user;"
        print("[load_user_df] 유저 데이터 쿼리 실행 중...")
        df = pd.read_sql(query, engine)
        print(f"[load_user_df] {len(df)}건 로드 완료")
        return df
    except Exception as e:
        print(f"[load_user_df] Error: {e}")
        return pd.DataFrame()

def load_log_df(path="data/raw/log_df.parquet"):
    try:
        df = pd.read_parquet(path)
        print(f"[load_log_df] {len(df)}건 로드 완료 from {path}")
        return df
    except Exception as e:
        print(f"[load_log_df] Error: {e}")
        return pd.DataFrame()

def save_book_df(book_df, path="data/raw/book_df.parquet"):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        book_df.to_parquet(path, index=False)
        print(f"[save_book_df] Saved to {path}")
    except Exception as e:
        print(f"[save_book_df] Error: {e}")

def save_user_df(user_df, path="data/raw/user_df.parquet"):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        user_df.to_parquet(path, index=False)
        print(f"[save_user_df] Saved to {path}")
    except Exception as e:
        print(f"[save_user_df] Error: {e}")

def save_log_df(log_df, path="data/raw/log_df.parquet"):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        log_df.to_parquet(path, index=False)
        print(f"[save_log_df] Saved to {path}")
    except Exception as e:
        print(f"[save_log_df] Error: {e}")


