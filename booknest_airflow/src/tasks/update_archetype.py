# assign_archetypes.py

import os
from sqlalchemy import create_engine, text
from collections import Counter
from utils.archetype_tag_map import archetype_tag_map  # 위에서 정의한 dict
from utils.db_utils import get_db_engine


def assign_user_archetypes():
    engine = get_db_engine()

    with engine.connect() as conn:
        # 1. 모든 Nest와 유저 가져오기
        result = conn.execute(text("""
            SELECT nest.id AS nest_id, user.id AS user_id
            FROM nest
            JOIN user ON nest.user_id = user.id
        """)).mappings().all()

        for row in result:
            nest_id = row["nest_id"]
            user_id = row["user_id"]

            # 2. 해당 유저의 nest에 담긴 책들의 태그 가져오기
            tag_result = conn.execute(text("""
                SELECT t.name
                FROM book_nest bn
                JOIN book_tag bt ON bt.book_id = bn.book_id
                JOIN tag t ON t.id = bt.tag_id
                WHERE bn.nest_id = :nest_id
            """), {"nest_id": nest_id}).mappings().all()

            if not tag_result:
                continue  # 책이 없으면 스킵
            tag_counter = Counter([r["name"] for r in tag_result])

            # 책 제목 + book_id 함께 조회
            book_info_result = conn.execute(text("""
                SELECT b.id AS book_id, b.title
                FROM book_nest bn
                JOIN book b ON b.id = bn.book_id
                WHERE bn.nest_id = :nest_id
            """), {"nest_id": nest_id}).mappings().all()

            # [(id, title), (id, title), ...] 형태로 변환
            book_infos = [(r["book_id"], r["title"]) for r in book_info_result]
            book_ids = [r["book_id"] for r in book_info_result]
            book_titles = [r["title"] for r in book_info_result]

            # 전체 태그 리스트
            all_tags = list(tag_counter.keys())

            #  출력
            print(f"\n User ID: {user_id}")
            print(f" Books in Nest: {book_infos}")
            print(f" Tags: {all_tags}")


            # 3. 아키타입 점수 계산
            archetype_scores = {}
            for archetype, tags in archetype_tag_map.items():
                archetype_scores[archetype] = sum(tag_counter[tag] for tag in tags)

            # 4. 가장 점수 높은 아키타입 선정
            best_fit = max(archetype_scores.items(), key=lambda x: x[1])[0]
            print(best_fit)
            # 5. 유저의 아키타입 업데이트
            conn.execute(text("""
                UPDATE user
                SET archetype = :archetype
                WHERE id = :user_id
            """), {"archetype": best_fit, "user_id": user_id})

        print(" 모든 유저의 아키타입이 성공적으로 업데이트되었습니다.")
