# src/modules/model_utils.py

import os
import pickle
import numpy as np
from lightfm import LightFM
from lightfm.cross_validation import random_train_test_split
from lightfm.evaluation import precision_at_k, recall_at_k, auc_score


def train_lightfm_model(interactions, weights, item_features, epochs=10):
    try:
        model = LightFM(loss="logistic", no_components=32, learning_rate=0.05)
        model.fit(
            interactions,
            sample_weight=weights,
            item_features=item_features,
            epochs=epochs,
            num_threads=4
        )
        print("[model_utils] 모델 학습 완료")
        return model
    except Exception as e:
        print(f"[model_utils] 모델 학습 실패: {e}")
        return None


def evaluate_model(model, interactions, item_features, k=5):
    try:
        print(f"[model_utils] 평가용 상호작용 행렬 shape: {interactions.shape}, nnz: {interactions.getnnz()}")

        train_eval, test_eval = random_train_test_split(interactions, test_percentage=0.05)

        if test_eval.nnz == 0:
            print("[model_utils] 평가 실패: 테스트 데이터가 비어있음")
            return

        precision = precision_at_k(model, test_eval, item_features=item_features, k=k).mean()
        recall = recall_at_k(model, test_eval, item_features=item_features, k=k).mean()
        auc = auc_score(model, test_eval, item_features=item_features).mean()

        print(f"[model_utils] Precision@{k}: {precision:.4f}")
        print(f"[model_utils] Recall@{k}: {recall:.4f}")
        print(f"[model_utils] AUC: {auc:.4f}")

    except Exception as e:
        print(f"[model_utils] 평가 실패: {e}")


def save_model(model, path="data/model/lightfm_model.pkl"):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(model, f)
        print(f"[model_utils] 모델 저장 완료: {path}")
    except Exception as e:
        print(f"[model_utils] 모델 저장 실패: {e}")
