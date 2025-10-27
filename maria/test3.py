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
CSV_FILE = "cleaned_books_concated.csv"
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

def process_many_to_many_bulk(cursor, book_id, items, table, bridge_table, cache_dict):
    insert_pairs = []

    for item in items:
        name = item.strip()
        if not name:
            continue
        item_id = insert_and_get_id(cursor, table, name, cache_dict)
        insert_pairs.append((book_id, item_id))

    if insert_pairs:
        cursor.executemany(
            f"INSERT INTO {bridge_table} (book_id, {table}_id) VALUES (?, ?)", 
            insert_pairs
        )

# ------------------ Main ------------------
def main():
    df = pd.read_csv(CSV_FILE, encoding=ENCODING)
    df = df.dropna(subset=["PUBLISHED_DATE"])  # book_id와 순서 일치 보장
    df = df.replace({np.nan: None})

    try:
        with connect_db() as conn:
            cursor = conn.cursor()

            author_dict = load_existing_dict(cursor, "author")
            category_dict = load_existing_dict(cursor, "category")
            tag_dict = load_existing_dict(cursor, "tag")

            for idx, (_, row) in enumerate(df.iterrows(), start=1):  # book_id는 1부터 시작
                book_id = idx

                if row.get("AUTHOR"):
                    authors = row["AUTHOR"].split(",")
                    process_many_to_many_bulk(cursor, book_id, authors, "author", "book_author", author_dict)

                if row.get("CATEGORY"):
                    categories = row["CATEGORY"].split(",")
                    process_many_to_many_bulk(cursor, book_id, categories, "category", "book_category", category_dict)

                if row.get("TAG"):
                    tags = row["TAG"].split(",")
                    process_many_to_many_bulk(cursor, book_id, tags, "tag", "book_tag", tag_dict)

                if idx % 100 == 0:
                    conn.commit()
                    print(f"{idx} rows processed...")

            conn.commit()
            print("✅ Many-to-many 관계 데이터 삽입 완료!")

    except mariadb.Error as e:
        print(f"❌ Database Error: {e}")
        conn.rollback()

if __name__ == "__main__":
    main()
