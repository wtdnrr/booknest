# src/tasks/update_model.py
import os
import pickle
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy.sparse import coo_matrix

from lightfm.data import Dataset
from modules.data_loader import load_user_df, load_book_df
from modules.model_utils import train_lightfm_model, evaluate_model, save_model
from utils.s3_utils import download_and_load_pickle_from_s3, upload_to_s3



def run():
    try:
        today = datetime.today()
        yesterday_str = (today - timedelta(days=1)).strftime("%Y%m%d")
        today_str = today.strftime("%Y%m%d")

        matrix_key = f"matrix/lightfm/matrix_lightfm_{today_str}.pkl"
        matrix_path = "data/processed/matrix_daily.pkl"

        print("[update_model] S3에서 전날 matrix.pkl 다운로드 중...")
        download_and_load_pickle_from_s3(
            s3_key=matrix_key,
            local_path=matrix_path,
            bucket_name="saffybooknest"
        )

        with open(matrix_path, "rb") as f:
            data = pickle.load(f)

        print("[update_model] 기존 데이터 로딩 완료")
        dataset: Dataset = data["dataset"]
        interactions = data["interactions"]
        weights = data["weights"]
        item_features = data["item_features"]
        user_mapping = data.get("user_mapping", {})
        item_mapping = data.get("item_mapping", {})

        user_df = load_user_df()
        book_df = load_book_df()

        all_user_ids = user_df["id"].unique().tolist()
        all_book_ids = book_df["book_id"].unique().tolist()

        # 1️⃣ 일간 로그 데이터 (더미 예시)
        log_data = [
            {"user_id": 2, "book_id": 2, "action_type": "review_rating", "action_value": {"rating": 5}},
            {"user_id": 1, "book_id": 6, "action_type": "like", "action_value": None},
            {"user_id": 3, "book_id": 6688, "action_type": "like", "action_value": None},
        ]
        log_df = pd.DataFrame(log_data)

        action_weights = {
            "review_rating_5": 1.0, "review_rating_4": 0.9, "review_rating_3": 0.0,
            "review_rating_2": -0.3, "review_rating_1": -0.5,
            "rating_5": 1.0, "rating_4": 0.8, "rating_3": 0.0,
            "rating_2": -0.3, "rating_1": -0.5,
            "like": 0.9, "add_to_library": 0.8, "wishlist": 0.65,
        }

        def map_score(row):
            key = row["action_type"]
            if key == "review_rating":
                rating = row["action_value"].get("rating", 0)
                return action_weights.get(f"review_rating_{rating}", 0)
            elif key == "rating":
                return action_weights.get(f"rating_{row['action_value']}", 0)
            else:
                return action_weights.get(key, 0)

        log_df["score"] = log_df.apply(map_score, axis=1)
        log_df = log_df[log_df["score"] != 0]

        print(f"[update_model] 로그 {len(log_df)}건 반영 중...")

        # 2️⃣ 매핑되지 않은 유저/아이템 추가
        existing_users = set(user_mapping.keys())
        existing_items = set(item_mapping.keys())

        new_users = list(set(all_user_ids) - existing_users)
        new_items = list(set(all_book_ids) - existing_items)


        if new_users or new_items:
            print(f"[update_model] 신규 유저/아이템 추가 → users: {new_users}, items: {new_items}")
            dataset.fit_partial(
                users=new_users if new_users else None,
                items=new_items if new_items else None
            )
            # 갱신된 매핑 저장
            user_mapping = dataset.mapping()[0]
            item_mapping = dataset.mapping()[2]

        # 1. 매핑 시도
        log_df["user_index"] = log_df["user_id"].map(user_mapping)
        log_df["item_index"] = log_df["book_id"].map(item_mapping)

        # 2. 매핑 누락 제거
        log_df = log_df[log_df["user_index"].notnull() & log_df["item_index"].notnull()]

        # 3. 인덱스화
        log_df["user_index"] = log_df["user_index"].astype(int)
        log_df["item_index"] = log_df["item_index"].astype(int)

        # 4. coo_matrix 생성
        new_row = log_df["user_index"].values
        new_col = log_df["item_index"].values
        new_data = log_df["score"].values

        print(new_row)
        print(new_col)
        print(new_data)

        new_interactions = coo_matrix((np.ones_like(new_data), (new_row, new_col)), shape=interactions.shape)
        new_weights = coo_matrix((new_data, (new_row, new_col)), shape=weights.shape)

        # ✅ 디버깅 출력
        print("[디버깅] user_mapping:", user_mapping)
        print("[디버깅] item_mapping:", item_mapping)

        print("[update_model] 기존 interactions:")
        print(interactions)

        print("[update_model] 추가된 new_interactions:")
        print(new_interactions)

        # 4️⃣ Stack → Add로 변경 (덧셈)
        interactions = interactions + new_interactions
        weights = weights + new_weights

        interactions = interactions.tocoo()
        weights = weights.tocoo()

        print("[update_model] 병합된 interactions:")
        print(interactions)

        # 5️⃣ 학습 및 저장
        print("[update_model] 모델 업데이트 학습 중...")
        model = train_lightfm_model(interactions, weights, item_features)
        evaluate_model(model, interactions, item_features)

        model_path = "model/lightfm_model_updated.pkl"
        save_model(model, path=model_path)

        upload_to_s3(
            file_path=model_path,
            bucket_name="saffybooknest",
            s3_key=f"model/lightfm/model_lightfm_{today_str}_updated.pkl"
        )
        print(f"[update_model] 업데이트 모델 S3 저장 완료")

        # 📌 업데이트된 메트릭스도 저장
        updated_matrix_path = "data/processed/matrix_updated.pkl"
        with open(updated_matrix_path, "wb") as f:
            pickle.dump({
                "interactions": interactions.tocoo(),
                "weights": weights.tocoo(),
                "item_features": item_features,
                "dataset": dataset,
                "user_mapping": user_mapping,
                "item_mapping": item_mapping,
            }, f)

        upload_to_s3(
            file_path=updated_matrix_path,
            bucket_name="saffybooknest",
            s3_key=f"matrix/lightfm/matrix_lightfm_{today_str}_updated.pkl"
        )
        print("[update_model] 업데이트된 메트릭스도 S3에 저장 완료")

    except Exception as e:
        print(f"[update_model] 오류 발생: {e}")
        sys.exit(1)
