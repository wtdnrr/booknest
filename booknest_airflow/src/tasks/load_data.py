import os
from datetime import datetime
from utils.db_utils import get_db_engine
from utils.s3_utils import load_csv_from_s3
from modules.data_loader import (
    load_book_df, load_user_df,
    save_book_df, save_user_df, save_log_df
)

def run():
    try:
        print("[load_data] DB 연결 중...")
        engine = get_db_engine()

        os.makedirs("data/raw", exist_ok=True)
        print("[load_data] 저장 경로(data/raw) 확인 완료")

        print("[load_data] 도서 정보 로딩 중...")
        book_df = load_book_df()
        print(f"[load_data] 도서 정보 {len(book_df)}건 로드 완료")

        print("[load_data] 유저 정보 로딩 중...")
        user_df = load_user_df()
        print(f"[load_data] 유저 정보 {len(user_df)}건 로드 완료")

        today_str = datetime.today().strftime("%y%m%d")
        s3_key = f"logs/250411/logs_250411.csv"
        local_path = f"data/raw/logs_{today_str}.csv"

        print(f"[load_data] 로그 S3 다운로드 중 → {s3_key}")
        log_df = load_csv_from_s3("saffybooknest", s3_key, local_path)

        # # 인기 도서 필터링 예시 (아직 적용하지 않음)
        # top_books = log_df['book_id'].value_counts().head(1000).index
        # book_df = book_df[book_df['book_id'].isin(top_books)]
        # print(f"[load_data] 인기 도서 필터링 후: {len(book_df)}권")

        print("[load_data] 파일 저장 중...")
        save_book_df(book_df)
        save_user_df(user_df)
        save_log_df(log_df)
        print("[load_data] 저장 완료")

    except Exception as e:
        print(f"[load_data] 오류 발생: {e}")
        import sys
        sys.exit(1)