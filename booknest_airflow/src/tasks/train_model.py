# src/tasks/train_model.py

import os
import sys
import pickle
import numpy as np
from datetime import datetime
from modules.model_utils import train_lightfm_model, evaluate_model, save_model
from utils.s3_utils import upload_to_s3


def run():
    try:
        os.makedirs("data/model", exist_ok=True)

        print("[train_model] 학습용 행렬 로드 중...")
        with open("data/processed/matrix.pkl", "rb") as f:
            data = pickle.load(f)

        interactions = data["interactions"]
        weights = data["weights"]
        item_features = data["item_features"]
        user_mapping = data.get("user_mapping", {})
        item_mapping = data.get("item_mapping", {})

        print(f"[train_model] user 수: {len(user_mapping)}, item 수: {len(item_mapping)}")
        print(f"[train_model] interactions shape: {interactions.shape}, nnz: {interactions.nnz}")

        print("[train_model] 모델 학습 시작...")
        model = train_lightfm_model(interactions, weights, item_features)

        print(model.item_embeddings.shape[0])

        if model is None:
            raise ValueError("모델 학습 실패: 반환된 모델이 None입니다.")

        # 유저 벡터 차이 출력 (디버깅용)
        if len(user_mapping) >= 2:
            user_vecs = model.user_embeddings
            print("[train_model] user 0 vs 1 벡터 차이:", np.linalg.norm(user_vecs[0] - user_vecs[1]))

        print("[train_model] Precision@5 평가 중...")
        evaluate_model(model, interactions, item_features, k=5)

        model_path = "data/model/lightfm_model.pkl"
        save_model(model, model_path)

        print(f"[train_model] 모델 로컬 저장 경로: {model_path}")
        print(f"[train_model] 현재 작업 디렉토리: {os.getcwd()}")

        today_str = datetime.today().strftime("%Y%m%d")
        s3_key = f"model/lightfm/model_lightfm_{today_str}.pkl"
        upload_to_s3(model_path, "saffybooknest", s3_key)
        print(f"[train_model] [모델 S3 업로드 완료 → s3://saffybooknest/{s3_key}")

    except Exception as e:
        print(f"[train_model] 에러 발생: {e}")
        sys.exit(1)
