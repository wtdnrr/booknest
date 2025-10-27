import pandas as pd


data_processed = pd.read_csv("data_processed/page_1/NL_BO_BOOK_PUB_202402-1_processed.csv")
data_tagged = pd.read_csv("data_tagged/page_1/NL_BO_BOOK_PUB_202402-1_tagged.csv")


# data_processed['ISBN_THIRTEEN_NO'] = pd.to_numeric(data_processed['ISBN_THIRTEEN_NO'], errors='coerce').astype('Int64')

merged_df = pd.merge(data_processed, data_tagged, left_on="ISBN_THIRTEEN_NO", right_on="ISBN", how="left")

# column_mapping = {
#     "AUTHR_NM": "author", 
#     "PUBLISHER": "publisher",
#     "PBLICTE_YEAR": "published_date",
#     "TITLE_NM": "title",
#     "ISBN_THIRTEEN_NO": "isbn_no",
#     "ISBN": "isbn",
#     "BOOK_IMAGE": "image_url",
#     "CATEGORY": "category",
#     "INTRO": "intro",
#     "CONTENTS": "index",
#     "PUBLISHER_REVIEW": "publisher_review",
#     "BOOK_PAGE": "pages",
#     "TAGS": "tag"
# }

# merged_df.rename(columns=column_mapping, inplace=True)
df_filtered = merged_df.drop(columns=['ISBN_THIRTEEN_NO'])

df_filtered.to_csv("test_data.csv", index=False, encoding="utf-8")
