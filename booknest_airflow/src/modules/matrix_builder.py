from lightfm.data import Dataset
import pandas as pd

# 점수 매핑 테이블
ACTION_SCORES = {
    "rating_star_5": 5000,
    "rating_star_4": 3000,
    "rating_star_3": 1000,
    "rating_star_2": -1500,
    "rating_star_1": -2500,
    "rating_cancel_5": -5000,
    "rating_cancel_4": -3000,
    "rating_cancel_3": -1000,
    "rating_cancel_2": 1500,
    "rating_cancel_1": 2500,
    "update_rating_star_1_2": 2500 - 1500,
    "update_rating_star_1_3": 2500 + 1000,
    "update_rating_star_1_4": 2500 + 3000,
    "update_rating_star_1_5": 2500 + 5000,
    "update_rating_star_2_1": 1500 - 2500,
    "update_rating_star_2_3": 1500 + 1000,
    "update_rating_star_2_4": 1500 + 3000,
    "update_rating_star_2_5": 1500 + 5000,
    "update_rating_star_3_1": -1000 - 2500,
    "update_rating_star_3_2": -1000 - 1500,
    "update_rating_star_3_4": -1000 + 3000,
    "update_rating_star_3_5": -1000 + 5000,
    "update_rating_star_4_1": -3000 - 2500,
    "update_rating_star_4_2": -3000 - 1500,
    "update_rating_star_4_3": -3000 + 3000,
    "update_rating_star_4_5": -3000 + 5000,
    "update_rating_star_5_1": -5000 - 2500,
    "update_rating_star_5_2": -5000 - 1500,
    "update_rating_star_5_3": -5000 + 1000,
    "update_rating_star_5_4": -5000 + 3000,
    "add_to_bookshelf": 4000,
    "cancel_bookshelf": -4000,
    "add_to_wishlist": 3250,
    "cancel_wishlist": -3250,
    "click_book_detail": 2000,
    "click_dislike": -5000,
}

def map_interaction_score(row):
    return ACTION_SCORES.get(row["action_type"], 0)

def build_matrix(user_df, book_df, log_df):
    try:
        # 점수 매핑 및 필터링
        log_df["score"] = log_df.apply(map_interaction_score, axis=1)
        log_df = log_df[log_df["score"] != 0]

        # 상호작용이 있는 유저/책만 사용
        log_df = log_df[
            log_df["user_id"].isin(user_df["user_id"]) &
            log_df["book_id"].isin(book_df["book_id"])
        ]

        print(f"[matrix_builder] 유효한 상호작용 수: {len(log_df)}")

        dataset = Dataset()
        dataset.fit(
            users=user_df["user_id"].unique(),
            items=log_df["book_id"].unique(),  # 상호작용 있는 책만
            item_features=set(tag for tags in book_df["feature_list"] for tag in tags)
        )

        # 전체 유저, 전체 책 포함
        # dataset.fit(
        #     users=user_df["user_id"].unique(),
        #     items=book_df["book_id"].unique(),
        #     item_features=set(tag for tags in book_df["feature_list"] for tag in tags)
        # )

        interactions_data = list(zip(log_df["user_id"], log_df["book_id"], log_df["score"]))
        interactions, weights = dataset.build_interactions(interactions_data)

        used_books = book_df[book_df["book_id"].isin(log_df["book_id"])]
        item_features_data = [(row.book_id, row.feature_list) for row in used_books.itertuples()]
        item_features = dataset.build_item_features(item_features_data)

        # 전체 책의 feature 포함
        # item_features_data = [(row.book_id, row.feature_list) for row in book_df.itertuples()]
        # item_features = dataset.build_item_features(item_features_data)

        user_mapping = dataset.mapping()[0]
        item_mapping = dataset.mapping()[2]


        print(f"[matrix_builder] 사용자 수: {len(user_mapping)}")
        print(f"[matrix_builder] 학습에 사용된 책 수: {len(item_mapping)}")

        return interactions, weights, item_features, dataset, user_mapping, item_mapping

    except Exception as e:
        print(f"[matrix_builder] 오류 발생: {e}")
        return None, None, None, None, {}, {}
