# -*- coding: utf-8 -*-
import mariadb
import pandas as pd
import numpy as np

# ------------------ Config ------------------
DB_CONFIG = {
    "host": "43.203.172.46",
    "port": 3306,
    "user": "",
    "password": "",
    "database": ""
}
CSV_FILE = "../cleaned_books_concated.csv"
ENCODING = 'utf-8'

# ------------------ DB Helper ------------------
def connect_db():
    conn = mariadb.connect(**DB_CONFIG)
    conn.cursor().execute("SET NAMES utf8mb4")
    return conn

def load_existing_dict(cursor, table):
    cursor.execute(f"SELECT id, name FROM {table}")
    return {name: id for id, name in cursor.fetchall()}

def insert_and_get_id(cursor, table, name, cache_dict):
    if name not in cache_dict:
        cursor.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,))
        cache_dict[name] = cursor.lastrowid
    return cache_dict[name]

def insert_book(cursor, row):
    try:
        # DEBUG: 파라미터 준비
        params = (
            row["TITLE"] or "",
            row["PUBLISHED_DATE"],
            row["ISBN"] or None,
            row["PUBLISHER"] or "",
            row["PAGE"] or "",
            row["BOOK_IMAGE"] or "",
            row["INTRO"] or "",
            row["CONTENTS"] or "",
            row["TOTAL_RATINGS"] or "",
            str(row["PUBLISHER_REVIEW"]) if row["PUBLISHER_REVIEW"] is not None else ""
        )

        # DEBUG: 컬럼 이름 리스트 (순서 맞게!)
        param_names = [
            "title", "published_date", "isbn", "publisher",
            "pages", "image_url", "intro", "book_index", "publisher_review", "total_ratings"
        ]

        # INSERT 실행
        cursor.execute("""
            INSERT INTO book (
                title, published_date, isbn, publisher,
                pages, image_url, intro, book_index,
                publisher_review, total_ratings, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
        """, params)

        return cursor.lastrowid

    except Exception as e:
        print("에러 발생! 해당 row 정보 ↓↓↓")
        print("row dict:", row.to_dict())  # 전체 row 값
        print("\n파라미터 디버깅:")
        for name, val in zip(param_names, params):
            val_str = val if val is not None else "None"
            print(f"  {name:<17}: {val_str!r} (len: {len(val_str) if isinstance(val_str, str) else 'n/a'})")

        raise  # 에러 다시 던져서 트레이스백 유지


def process_many_to_many(cursor, book_id, items, table, bridge_table, cache_dict):
    for item in items:
        name = item.strip()
        if name:
            item_id = insert_and_get_id(cursor, table, name, cache_dict)
            cursor.execute(f"INSERT INTO {bridge_table} (book_id, {table}_id) VALUES (?, ?)", (book_id, item_id))

# ------------------ Main ------------------
def main():
    df = pd.read_csv(CSV_FILE, encoding=ENCODING, dtype={"PUBLISHED_DATE": "Int64"})
    # df = df[df["STATUS"] == "SUCCESS"].replace({np.nan: None})
    df = df.replace({np.nan: None})
    print(f"Processing {len(df)} rows")
    df['PUBLISHED_DATE'] = df['PUBLISHED_DATE'].astype("Int64")
    print(df.info())

    print(df['PUBLISHED_DATE'].head())
    df = df[]
    BATCH_SIZE = 1000

    try:
        with connect_db() as conn:
            cursor = conn.cursor()

            author_dict = load_existing_dict(cursor, "author")
            category_dict = load_existing_dict(cursor, "category")
            tag_dict = load_existing_dict(cursor, "tag")

            total = len(df)
            for batch_start in range(0, total, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total)
                batch_df = df.iloc[batch_start:batch_end]

                for idx, (_, row) in enumerate(batch_df.iterrows(), start=batch_start + 1):
                    book_id = insert_book(cursor, row)

                    if row["AUTHOR"]:
                        authors = row["AUTHOR"].split(",")
                        process_many_to_many(cursor, book_id, authors, "author", "book_author", author_dict)

                    if row["CATEGORY"]:
                        categories = row["CATEGORY"].split(",")
                        process_many_to_many(cursor, book_id, categories, "category", "book_category", category_dict)

                    if row.get("TAG"):
                        tags = row["TAG"].split(",")
                        process_many_to_many(cursor, book_id, tags, "tag", "book_tag", tag_dict)

                conn.commit()
                print(f"{batch_end}/{total} rows processed ({(batch_end/total)*100:.2f}%)")

            print("전체 데이터 삽입 완료!")

    except mariadb.Error as e:
        print(f"Database Error: {e}")
        conn.rollback()



if __name__ == "__main__":
    main()