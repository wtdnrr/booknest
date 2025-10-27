# # app/internal/recommendations_logic.py
# from sqlalchemy import bindparam, text
# import pandas as pd
# import numpy as np
# from lightfm import LightFM
# from lightfm.data import Dataset
# import tempfile
# import pickle
# from app.dependencies import get_s3_client
# from datetime import datetime
# from app import config


# def download_and_load_pickle_from_s3(s3_key: str):
#     try:
#         s3 = get_s3_client()
#         with tempfile.NamedTemporaryFile() as tmp:
#             s3.download_file(config.S3_BUCKET_NAME, s3_key, tmp.name)
#             with open(tmp.name, "rb") as f:
#                 return pickle.load(f)
#     except Exception as e:
#         raise RuntimeError(f"[S3] 다운로드 실패: {e}")


# def get_today_recommendations(db, user_id: int, top_n: int = 15):
#     print("S3에서 모델 및 행렬 로드 중...")
#     today_str = datetime.today().strftime("%Y%m%d")
#     matrix = download_and_load_pickle_from_s3(f"matrix/lightfm/matrix_lightfm_{today_str}.pkl")
#     model = download_and_load_pickle_from_s3(f"model/lightfm/model_lightfm_{today_str}.pkl")

#     user_mapping = matrix["user_mapping"]
#     item_mapping = matrix["item_mapping"]
#     item_features = matrix["item_features"]

#     if user_id not in user_mapping:
#         raise ValueError("해당 유저의 추천 정보를 찾을 수 없습니다.")

#     user_index = user_mapping[user_id]
#     n_items = len(item_mapping)

#     print("[추천] LightFM 점수 계산 중...")
#     scores = model.predict(user_index, np.arange(n_items), item_features=item_features)
#     top_items = np.argsort(-scores)[:top_n]
#     reverse_item_mapping = {v: k for k, v in item_mapping.items()}
#     scored_books = [(int(reverse_item_mapping[i]), scores[i]) for i in top_items]

#     print("[추천 점수 출력]")
#     for book_id, score in scored_books:
#         print(f"book_id: {book_id}, score: {score:.4f}")

#     print(f"[추천 완료] 추천 도서 ID 목록: {[book_id for book_id, _ in scored_books]}")

#     book_infos = db.execute(
#         text("""
#             SELECT 
#                 B.id AS book_id,
#                 B.title AS title,
#                 B.image_url AS image_url,
#                 B.published_date AS published_date,
#                 B.isbn AS isbn,
#                 B.publisher AS publisher,
#                 B.pages AS pages,
#                 B.intro AS intro,
#                 B.book_index AS index_content,
#                 B.publisher_review AS publisher_review,
#                 GROUP_CONCAT(DISTINCT A.name) AS authors,
#                 GROUP_CONCAT(DISTINCT C.name) AS categories,
#                 GROUP_CONCAT(DISTINCT T.name) AS tags
#             FROM book B
#             LEFT JOIN book_author BA ON B.id = BA.book_id
#             LEFT JOIN author A ON BA.author_id = A.id
#             LEFT JOIN book_category BC ON B.id = BC.book_id
#             LEFT JOIN category C ON BC.category_id = C.id
#             LEFT JOIN book_tag BT ON B.id = BT.book_id
#             LEFT JOIN tag T ON BT.tag_id = T.id
#             WHERE B.id IN :ids
#             GROUP BY B.id
#         """).bindparams(bindparam("ids", expanding=True)),
#         {"ids": [book_id for book_id, _ in scored_books]}
#     ).fetchall()

#     book_info_dict = {row.book_id: row._mapping for row in book_infos}

#     return [
#         dict(book_info_dict[book_id])
#         for book_id, _ in scored_books
#         if book_id in book_info_dict
#     ]


# def cosine_similarity(vec1, vec2):
#     if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
#         return 0.0
#     return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# def get_recent_tag_recommendations(db, redis, user_id, top_k: int = 5):
#     key = f"user:{user_id}:tag_vector"
#     result = redis.zrevrange(key, 0, -1, withscores=True)

#     user_vector = dict(result)

#     if not user_vector:
#         return {"message": f"No vector found for user {user_id}"}

#     sorted_tags = sorted(user_vector.items(), key=lambda x: x[1], reverse=True)[:5]
#     sorted_tag_names = [tag for tag, _ in sorted_tags]
#     print(f"User's Top 5 Tags: {sorted_tag_names}")

#     tag_placeholders = ", ".join([f"'{tag}'" for tag in sorted_tag_names])
#     candidate_books = db.execute(
#         text(f"""
#             SELECT 
#                 B.id AS book_id,
#                 B.isbn AS isbn,
#                 GROUP_CONCAT(DISTINCT T.name) AS tags
#             FROM book B
#             LEFT JOIN book_tag BT ON B.id = BT.book_id
#             LEFT JOIN tag T ON BT.tag_id = T.id
#             WHERE T.name IN ({tag_placeholders})
#             GROUP BY B.id
#         """)
#     ).mappings().fetchall()

#     recommended_books = []
#     seen_isbns = set()

#     for book in candidate_books:
#         isbn = book["isbn"]
#         if isbn in seen_isbns:
#             continue

#         book_tags = book["tags"].split(",") if book["tags"] else []
#         book_tag_vector = np.array([1.0 if tag in book_tags else 0.0 for tag in sorted_tag_names])
#         user_vector_array = np.array([user_vector.get(tag, 0.0) for tag in sorted_tag_names])

#         score = cosine_similarity(user_vector_array, book_tag_vector)

#         if score > 0.0:
#             recommended_books.append((book["book_id"], score))
#             seen_isbns.add(isbn)

#         if len(recommended_books) >= top_k:
#             break

#     if not recommended_books:
#         return {"user_id": user_id, "recommendations": []}

#     recommended_books.sort(key=lambda x: x[1], reverse=True)
#     recommended_ids = [book_id for book_id, _ in recommended_books]

#     book_infos = db.execute(
#         text("""
#             SELECT 
#                 B.id AS book_id,
#                 B.title AS title,
#                 B.image_url AS image_url,
#                 B.published_date AS published_date,
#                 B.isbn AS isbn,
#                 B.publisher AS publisher,
#                 B.pages AS pages,
#                 B.intro AS intro,
#                 B.book_index AS index_content,
#                 B.publisher_review AS publisher_review,
#                 GROUP_CONCAT(DISTINCT A.name) AS authors,
#                 GROUP_CONCAT(DISTINCT C.name) AS categories,
#                 GROUP_CONCAT(DISTINCT T.name) AS tags
#             FROM book B
#             LEFT JOIN book_author BA ON B.id = BA.book_id
#             LEFT JOIN author A ON BA.author_id = A.id
#             LEFT JOIN book_category BC ON B.id = BC.book_id
#             LEFT JOIN category C ON BC.category_id = C.id
#             LEFT JOIN book_tag BT ON B.id = BT.book_id
#             LEFT JOIN tag T ON BT.tag_id = T.id
#             WHERE B.id IN :ids
#             GROUP BY B.id
#         """).bindparams(bindparam("ids", expanding=True)),
#         {"ids": recommended_ids}
#     ).fetchall()

#     book_info_dict = {row.book_id: row._mapping for row in book_infos}

#     return [
#         dict(book_info_dict[book_id])
#         for book_id, _ in recommended_books
#         if book_id in book_info_dict
#     ]


from datetime import datetime
import tempfile
import pickle
import numpy as np
from app.dependencies import get_s3_client
from elasticsearch import Elasticsearch
from app import config


def download_and_load_pickle_from_s3(s3_key: str):
    try:
        s3 = get_s3_client()
        with tempfile.NamedTemporaryFile() as tmp:
            s3.download_file(config.S3_BUCKET_NAME, s3_key, tmp.name)
            with open(tmp.name, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        raise RuntimeError(f"[S3] 다운로드 실패: {e}")


def get_today_recommendations(es: Elasticsearch, user_id: int, top_n: int = 15):
    print("S3에서 모델 및 행렬 로드 중...")
    today_str = datetime.today().strftime("%Y%m%d")
    matrix = download_and_load_pickle_from_s3(f"matrix/lightfm/matrix_lightfm_{today_str}.pkl")
    model = download_and_load_pickle_from_s3(f"model/lightfm/model_lightfm_{today_str}.pkl")

    user_mapping = matrix["user_mapping"]
    item_mapping = matrix["item_mapping"]
    item_features = matrix["item_features"]

    if user_id not in user_mapping:
        raise ValueError("해당 유저의 추천 정보를 찾을 수 없습니다.")

    user_index = user_mapping[user_id]
    n_items = len(item_mapping)

    print("[추천] LightFM 점수 계산 중...")
    scores = model.predict(user_index, np.arange(n_items), item_features=item_features)
    top_items = np.argsort(-scores)[:top_n]
    reverse_item_mapping = {v: k for k, v in item_mapping.items()}
    scored_books = [(int(reverse_item_mapping[i]), scores[i]) for i in top_items]

    print(f"[추천 완료] 추천 도서 ID 목록: {[book_id for book_id, _ in scored_books]}")

    book_ids = [str(book_id) for book_id, _ in scored_books]

    resp = es.search(
        index="book",
        query={"terms": {"_id": book_ids}},
        size=top_n
    )

    book_dict = {
        int(hit["_id"]): {
            **hit["_source"],
            "book_id": int(hit["_id"]),
            "authors": ", ".join([a for a in hit["_source"].get("authors", []) if isinstance(a, str)]),
            "tags": ", ".join([
                t if t != "_tagsparsefailure" else "" 
                for t in hit["_source"].get("tags", []) 
                if isinstance(t, str)
            ]),
        }
        for hit in resp["hits"]["hits"]
    }

    return [
        book_dict[book_id]
        for book_id, _ in scored_books
        if book_id in book_dict
    ]


def cosine_similarity(vec1, vec2):
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def get_recent_tag_recommendations(redis, es: Elasticsearch, user_id, top_k: int = 15):
    key = f"user:{user_id}:tag_vector"
    result = redis.zrevrange(key, 0, -1, withscores=True)

    user_vector = dict(result)
    if not user_vector:
        return {"message": f"No vector found for user {user_id}"}

    sorted_tags = sorted(
        [(tag, score) for tag, score in user_vector.items() if tag is not None],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    sorted_tag_names = [tag for tag, _ in sorted_tags]

    print(f"[사용자 {user_id}] 상위 태그: {sorted_tag_names}")

    resp = es.search(
        index="book",
        query={
            "terms": {
                "tags": sorted_tag_names
            }
        },
        size=1000
    )

    recommended_books = []
    seen_book_ids = set()

    for hit in resp["hits"]["hits"]:
        doc = hit["_source"]
        book_id = int(hit["_id"])
        tags = doc.get("tags") or []

        if book_id in seen_book_ids:
            continue

        book_tag_vector = np.array([1.0 if tag in tags else 0.0 for tag in sorted_tag_names])
        user_vector_array = np.array([user_vector.get(tag, 0.0) for tag in sorted_tag_names])
        score = cosine_similarity(user_vector_array, book_tag_vector)

        if score > 0.0:
            recommended_books.append((book_id, score))
            seen_book_ids.add(book_id)

    recommended_books.sort(key=lambda x: x[1], reverse=True)
    recommended_books = recommended_books[:top_k]
    book_ids = [str(book_id) for book_id, _ in recommended_books]

    final_resp = es.search(
        index="book",
        query={"terms": {"_id": book_ids}},
        size=len(book_ids)
    )

    # book_dict = {
    #     int(hit["_id"]): hit["_source"] | {"book_id": int(hit["_id"])}
    #     for hit in final_resp["hits"]["hits"]
    # }

    book_dict = {
        int(hit["_id"]): {
            **hit["_source"],
            "book_id": int(hit["_id"]),
            "authors": ", ".join(hit["_source"].get("authors", [])),
            "tags": ", ".join(hit["_source"].get("tags", [])),
        }
        for hit in final_resp["hits"]["hits"]
    }

    results = []
    for book_id, score in recommended_books:
        book = book_dict.get(book_id)
        if not book:
            continue

        # 콘솔에 출력
        print(f'[추천 도서] book_id: {book_id}, title: "{book.get("title", "")}", score: {score:.4f}')

        results.append(book)

    return results