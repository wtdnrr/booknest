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
SKIPPED_ROWS = {17147}  # CSV 인덱스 기준으로 누락된 행 번호를 넣음 (0부터 시작)

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
    df = df.dropna(subset=["PUBLISHED_DATE", "ISBN"])
    df = df.replace({np.nan: None})

    total_rows = len(df)

    try:
        with connect_db() as conn:
            cursor = conn.cursor()

            author_dict = load_existing_dict(cursor, "author")
            category_dict = load_existing_dict(cursor, "category")
            tag_dict = load_existing_dict(cursor, "tag")

            skipped_count = 0

            for idx, row in enumerate(df.itertuples(index=True), start=1):
                if row.Index in SKIPPED_ROWS:
                    skipped_count += 1
                    print(f"[{idx}/{total_rows}] ⏭️ 누락된 행 (index {row.Index}) — 건너뜀")
                    continue

                book_id = idx - skipped_count  # 순서대로 맞춰진 book_id

                if row.AUTHOR:
                    authors = row.AUTHOR.split(",")
                    process_many_to_many_bulk(cursor, book_id, authors, "author", "book_author", author_dict)

                if row.CATEGORY:
                    categories = row.CATEGORY.split(",")
                    process_many_to_many_bulk(cursor, book_id, categories, "category", "book_category", category_dict)

                if row.TAG:
                    tags = row.TAG.split(",")
                    process_many_to_many_bulk(cursor, book_id, tags, "tag", "book_tag", tag_dict)

                if idx % 100 == 0 or idx == total_rows:
                    print(f"✅ [{idx}/{total_rows}] rows processed... (skipped: {skipped_count})")

            conn.commit()
            print("🎉 many-to-many 관계 삽입 완료 (누락된 행 제외)!")

    except mariadb.Error as e:
        print(f"❌ Database Error: {e}")
        conn.rollback()

if __name__ == "__main__":
    main()
