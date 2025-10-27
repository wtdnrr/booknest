import pandas as pd


# df = pd.read_csv("../data/bookdata_crawled/bookdata_crawled_top_loan.csv", dtype={"PUBLISHED_DATE": "Int64"})
# df = pd.read_csv("../FINALDATA/cleaned_books_steady.csv")
df = pd.read_csv("../pipeline/merged_output.csv")


print(df.info())


# ─────────────────────────────
# 🔹 '세트' 포함된 책 제거
set_books = df[df['TITLE'].str.contains('세트', na=False)]
df = df[~df['TITLE'].str.contains('세트', na=False)]
set_books[['TITLE']].to_csv("removed_set_books.csv", index=False)

# ─────────────────────────────
# 🔹 시리즈 처리
df[['BASE_TITLE', 'SERIES_NUM']] = df['TITLE'].str.extract(r'^(.*)\s(\d+)$')
is_series = df['BASE_TITLE'].notna()
series_df = df[is_series].copy()
series_df['SERIES_NUM'] = series_df['SERIES_NUM'].astype(int)
series_df_sorted = series_df.sort_values(['BASE_TITLE', 'SERIES_NUM'])
first_books = series_df_sorted.drop_duplicates('BASE_TITLE', keep='first')
removed_books = pd.merge(series_df_sorted, first_books, how='outer', indicator=True).query('_merge == "left_only"')
removed_books[['TITLE']].to_csv("removed_books.csv", index=False)
first_books['TITLE'] = first_books['BASE_TITLE']
non_series_df = df[~is_series].copy()
df = pd.concat([non_series_df, first_books], ignore_index=True).drop(columns=['BASE_TITLE', 'SERIES_NUM'], errors='ignore')

# ─────────────────────────────
# 🔹 번역가 제거 로직
def clean_authors(author_str):
    if pd.isna(author_str) or ',' not in author_str:
        return author_str, False
    
    authors = [a.strip() for a in author_str.split(',')]
    three_char_names = [a for a in authors if (len(a) == 3) or (len(a) == 2)]
    spaced_names = [a for a in authors if ' ' in a]

    # 기준에 맞으면 3글자 이름 제거
    if spaced_names and three_char_names:
        new_authors = [a for a in authors if a not in three_char_names]
        return ', '.join(new_authors), True
    return author_str, False

# 적용 및 변경사항 추적
df['AUTHOR_NEW'], changed = zip(*df['AUTHOR'].apply(clean_authors))
df['AUTHOR'] = df['AUTHOR_NEW']
df = df.drop(columns='AUTHOR_NEW')

# 변경된 항목만 따로 저장
changed_df = df[list(changed)]
changed_df[['TITLE', 'AUTHOR']].to_csv("author_cleaned_books.csv", index=False)


# ─────────────────────────────
# 🔹 작가 접미어 제거 (' 등', ' 외', ' 엮음')
unwanted_suffixes = [' 등', ' 외', ' 엮음']

def clean_author_suffixes(authors):
    cleaned = []
    for name in str(authors).split(","):
        name = name.strip()
        for suffix in unwanted_suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        if name:
            cleaned.append(name)
    return ", ".join(cleaned)

df['AUTHOR'] = df['AUTHOR'].apply(clean_author_suffixes)

# ─────────────────────────────
# 🔹 최종 정리된 데이터 저장
df.to_csv("cleaned_books.csv", index=False)

print("✅ '세트' 책 제거 → removed_set_books.csv")
print("✅ 시리즈 책 제거 → removed_books.csv")
print("✅ 번역가 제거된 책 → author_cleaned_books.csv")
print("✅ 최종 정리된 데이터 → cleaned_books.csv")