import mariadb
import pandas as pd
import numpy as np
from collections import defaultdict

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
BATCH_SIZE = 1000

# ------------------ DB Helper ------------------
def connect_db():
    conn = mariadb.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SET NAMES utf8mb4")
    cursor.close()
    return conn

def load_existing_dict(cursor, table):
    cursor.execute(f"SELECT id, name FROM {table}")
    return {name: id for id, name in cursor.fetchall()}

def load_book_ids_by_isbn(cursor):
    cursor.execute("SELECT id, isbn FROM book")
    return {isbn: id for id, isbn in cursor.fetchall()}

def insert_and_get_ids_batch(cursor, table, names, cache_dict):
    new_names = [name for name in names if name not in cache_dict]
    if not new_names:
        return

    values = [(name,) for name in new_names]
    cursor.executemany(f"INSERT IGNORE INTO {table} (name) VALUES (?)", values)

    # 다시 SELECT 해서 ID들 받아오기
    cursor.execute(f"SELECT id, name FROM {table} WHERE name IN ({','.join(['?']*len(new_names))})", new_names)
    for id, name in cursor.fetchall():
        cache_dict[name] = id

def process_many_to_many_bulk_batch(cursor, links, table, bridge_table):
    insert_pairs = list(set(links))  # 중복 제거
    if insert_pairs:
        cursor.executemany(
            f"INSERT IGNORE INTO {bridge_table} (book_id, {table}_id) VALUES (?, ?)",
            insert_pairs
        )

# ------------------ Main ------------------
def main():
    df = pd.read_csv(CSV_FILE, encoding=ENCODING)
    df = df.dropna(subset=["PUBLISHED_DATE", "ISBN"])
    df = df.replace({np.nan: None})
    total_rows = len(df)

    print(f"📚 총 {total_rows}건 처리 예정")

    try:
        with connect_db() as conn:
            cursor = conn.cursor()

            author_dict = load_existing_dict(cursor, "author")
            category_dict = load_existing_dict(cursor, "category")
            tag_dict = load_existing_dict(cursor, "tag")
            book_dict = load_book_ids_by_isbn(cursor)

            author_links = []
            category_links = []
            tag_links = []
            new_authors = set()
            new_categories = set()
            new_tags = set()

            for idx, row in enumerate(df.itertuples(index=False), start=1):
                isbn = str(row.ISBN).strip()
                book_id = book_dict.get(isbn)

                if not book_id:
                    print(f"[{idx}/{total_rows}] ⚠️ ISBN {isbn}에 해당하는 book_id 없음 — 건너뜀")
                    continue

                if row.AUTHOR:
                    authors = [a.strip() for a in row.AUTHOR.split(",") if a.strip()]
                    for name in authors:
                        new_authors.add(name)
                        author_links.append((book_id, name))

                if row.CATEGORY:
                    categories = [c.strip() for c in row.CATEGORY.split(",") if c.strip()]
                    for name in categories:
                        new_categories.add(name)
                        category_links.append((book_id, name))

                if row.TAG:
                    tags = [t.strip() for t in row.TAG.split(",") if t.strip()]
                    for name in tags:
                        new_tags.add(name)
                        tag_links.append((book_id, name))

                if idx % BATCH_SIZE == 0 or idx == total_rows:
                    print(f"🔄 [{idx}/{total_rows}] 데이터 처리 중...")

                    # 신규 항목 삽입
                    insert_and_get_ids_batch(cursor, "author", new_authors, author_dict)
                    insert_and_get_ids_batch(cursor, "category", new_categories, category_dict)
                    insert_and_get_ids_batch(cursor, "tag", new_tags, tag_dict)

                    # ID로 변환하여 관계 테이블 삽입
                    author_pairs = [(book_id, author_dict[name]) for book_id, name in author_links]
                    category_pairs = [(book_id, category_dict[name]) for book_id, name in category_links]
                    tag_pairs = [(book_id, tag_dict[name]) for book_id, name in tag_links]

                    process_many_to_many_bulk_batch(cursor, author_pairs, "author", "book_author")
                    process_many_to_many_bulk_batch(cursor, category_pairs, "category", "book_category")
                    process_many_to_many_bulk_batch(cursor, tag_pairs, "tag", "book_tag")

                    # 커밋 & 클리어
                    conn.commit()
                    author_links.clear()
                    category_links.clear()
                    tag_links.clear()
                    new_authors.clear()
                    new_categories.clear()
                    new_tags.clear()

                    print(f"✅ [{idx}/{total_rows}] 커밋 완료!")

            print("🎉 모든 many-to-many 관계 데이터 삽입 완료!")

    except mariadb.Error as e:
        print(f"🔥 예외 발생:\n{e}")
        try:
            conn.rollback()
        except:
            print("⚠️ 롤백 실패 (연결이 끊겼을 수도 있음)")

if __name__ == "__main__":
    main()
