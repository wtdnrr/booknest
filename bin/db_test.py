# -*- coding: utf-8 -*-
import mariadb
import pandas as pd
import numpy as np
import time

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
        print("🚨 삽입 중 에러 발생!")
        print("row dict:", row.to_dict())
        raise

def process_many_to_many(cursor, book_id, items, table, bridge_table, cache_dict):
    values_to_insert = []
    for item in items:
        name = item.strip()
        if name:
            item_id = insert_and_get_id(cursor, table, name, cache_dict)
            values_to_insert.append((book_id, item_id))

    if values_to_insert:
        cursor.executemany(
            f"INSERT INTO {bridge_table} (book_id, {table}_id) VALUES (?, ?)",
            values_to_insert
        )

# ------------------ Main ------------------
def main():
    df = pd.read_csv(CSV_FILE, encoding=ENCODING, dtype={"PUBLISHED_DATE": "Int64"})
    df = df.replace({np.nan: None})
    print(f"📚 Processing {len(df)} rows...")
    
    print(df.info())
    
    print(df["PUBLISHED_DATE"].head())

    BATCH_SIZE = 1000

    try:
        with connect_db() as conn:
            cursor = conn.cursor()

            author_dict = load_existing_dict(cursor, "author")
            category_dict = load_existing_dict(cursor, "category")
            tag_dict = load_existing_dict(cursor, "tag")

            total = len(df)
            inserted_count = 0
            start_time = time.time()

            for batch_start in range(0, total, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total)
                batch_df = df.iloc[batch_start:batch_end]

                for idx, (_, row) in enumerate(batch_df.iterrows(), start=batch_start + 1):
                    try:
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

                        inserted_count += 1

                    except Exception as e:
                        print(f"❌ {idx}: '{row['TITLE']}' 삽입 실패 - {e}")

                conn.commit()
                elapsed = time.time() - start_time
                progress = (batch_end / total) * 100
                print(f"✅ {batch_end}/{total} rows processed ({progress:.2f}%) | ⏱️ elapsed: {elapsed:.1f} sec")

            print(f"🎉 전체 삽입 완료: {inserted_count}건")

    except mariadb.Error as e:
        print(f"❗ Database Error: {e}")
        conn.rollback()

if __name__ == "__main__":
    main()
