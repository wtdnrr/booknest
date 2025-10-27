import os
import sys
import pickle
import pandas as pd
from datetime import datetime
from modules.feature_builder import build_feature_list
from modules.matrix_builder import build_matrix
from utils.s3_utils import upload_to_s3


def run():
    try:
        os.makedirs("data/processed", exist_ok=True)

        print("[build_matrix] 데이터 로딩 중...")
        book_df = pd.read_parquet("data/raw/book_df.parquet")
        log_df = pd.read_parquet("data/raw/log_df.parquet")
        user_df = pd.read_parquet("data/raw/user_df.parquet")

        print("[build_matrix] 피처 전처리 중...")
        book_df["feature_list"] = book_df.apply(build_feature_list, axis=1)

        print("[build_matrix] 행렬 생성 중...")
        interactions, weights, item_features, dataset, user_mapping, item_mapping = build_matrix(user_df, book_df, log_df)

        if interactions is None:
            raise ValueError("행렬 생성 실패")

        print("[build_matrix] 매핑된 상호작용 수:", interactions.nnz)

        save_path = "data/processed/matrix.pkl"
        with open(save_path, "wb") as f:
            pickle.dump({
                "interactions": interactions,
                "weights": weights,
                "item_features": item_features,
                "dataset": dataset,
                "user_mapping": user_mapping,
                "item_mapping": item_mapping,
            }, f)

        print(f"[build_matrix] 저장 완료: {save_path}")

        today_str = datetime.today().strftime("%Y%m%d")
        upload_to_s3(
            file_path=save_path,
            bucket_name="saffybooknest",
            s3_key=f"matrix/lightfm/matrix_lightfm_{today_str}.pkl"
        )
        print("[build_matrix] S3 업로드 완료")

    except Exception as e:
        print(f"[build_matrix] 오류 발생: {e}")
        sys.exit(1)
