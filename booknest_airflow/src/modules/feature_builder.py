# src/modules/feature_builder.py
import pandas as pd

def clean_split(x):
    return [i.strip() for i in str(x).split(",") if i.strip()]

def build_feature_list(row):
    features = []

    # 기존 방식 (한 가지 요소만 사용)
    # if pd.notna(row["tag"]):
    #     features += [f"tag:{t}" for t in clean_split(row["tag"])]
    # elif pd.notna(row["category"]):
    #     features += [f"category:{c}" for c in clean_split(row["category"])]
    # elif pd.notna(row["author"]):
    #     features.append(f"author:{row['author'].strip()}")

    # 개선된 방식: tag, category, author 모두 포함
    if pd.notna(row["tag"]):
        features += [f"tag:{t}" for t in clean_split(row["tag"])]
    if pd.notna(row["category"]):
        features += [f"category:{c}" for c in clean_split(row["category"])]
    if pd.notna(row["author"]):
        features.append(f"author:{row['author'].strip()}")

    return features or ["tag:기타"]

def apply_feature_engineering(book_df):
    try:
        book_df["feature_list"] = book_df.apply(build_feature_list, axis=1)
        print("[feature_builder] feature_list 생성 완료")
        return book_df
    except Exception as e:
        print(f"[feature_builder] feature_list 생성 오류: {e}")
        return book_df

