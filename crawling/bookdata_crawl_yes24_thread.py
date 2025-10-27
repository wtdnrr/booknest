import requests
import pandas as pd
from bs4 import BeautifulSoup
import sys
import os
import re
import time
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent

ua = UserAgent()
headers = {
    "User-Agent": ua.random
}


def safe_request(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            print(f"[ERROR] HTTP 오류 ({e}) - {url}")
            break  # 4xx는 재시도 안 함
        except requests.RequestException as e:
            print(f"[WARN] 요청 실패 ({e}), 재시도 {attempt + 1}/{retries}")
            time.sleep(delay)
    return None


def read_csv_subset(filename):
    try:
        df = pd.read_csv(filename, usecols=["ISBN_THIRTEEN_NO", "URL"])
        # df['KDC_NM'] = pd.to_numeric(df['KDC_NM'], errors='coerce')
        # df = df[(df['KDC_NM'] >= 800) & (df['KDC_NM'] < 900)]
        df = df[['ISBN_THIRTEEN_NO']]
        df['ISBN_THIRTEEN_NO'] = pd.to_numeric(df['ISBN_THIRTEEN_NO'], errors='coerce').astype('Int64')
        df = df.drop_duplicates().dropna()
        return df
    except Exception as e:
        print(f"[ERROR] CSV 파일 읽기 실패: {e}")
        return pd.DataFrame()


def get_book_page_url(book_isbn):
    search_url = f"https://www.yes24.com/product/search?domain=BOOK&query={book_isbn}"
    response = safe_request(search_url)
    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    if soup.find("div", class_="no_data_desc"):
        print(f"[WARN] ISBN {book_isbn}: 검색 결과 없음.")
        return None

    book_link = soup.select_one("div.info_name > a")
    return book_link["href"] if book_link else None


def get_book_info(book_url, book_isbn):
    if not book_url:
        return None

    full_url = "https://www.yes24.com" + book_url
    response = safe_request(full_url)
    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    try:
        title = soup.select_one("div.gd_titArea > h2")
        title = title.text.strip() if title else "N/A"

        author_raw = soup.select_one("span.gd_auth")
        author_text = author_raw.text.strip() if author_raw else "N/A"

        # 외 x명 및 감추기 처리
        if "정보 더 보기/감추기" in author_text:
            text = author_text.split("정보 더 보기/감추기")[-1]
            # 줄바꿈과 공백 기준으로 이름 추출
            names = [line.strip() for line in text.strip().splitlines() if line.strip()]
            # 쉼표로 연결된 문자열 반환
            author = ", ".join(names)
        else:
            # 기존 역할 제거 방식 유지
            roles = ['저', '저.', '그림', '그림.', '역', '역.', '글', '글.', '편', '편.', '감수', '감수.', '공.', '공', '등']
            author = []
            for part in re.split(r"/", author_text):
                for name in part.split(","):
                    name = name.strip()
                    for role in roles:
                        if name.endswith(role):
                            name = name[:-len(role)].strip()
                    if name:
                        author.append(name)
            author = ", ".join(author)

        publisher = soup.select_one("span.gd_pub > a")
        publisher = publisher.text.strip() if publisher else "N/A"

        published_date = soup.select_one("span.gd_date")
        published_date = published_date.text.split('년')[0].strip() if published_date else "N/A"

        image = soup.select_one("span.gd_img img")
        image_url = image["src"] if image else "N/A"

        page = ""
        page_table = soup.select_one("#infoset_specific table")
        if page_table:
            for row in page_table.select("tr"):
                th = row.select_one("th")
                if th and "쪽수" in th.text:
                    td = row.select_one("td")
                    page = td.text.split("쪽")[0].strip() if td else ""
                    break

        category_set = set()
        for dl in soup.select("dl.yesAlertDl"):
            dt = dl.select_one("dt")
            if dt and dt.get_text(strip=True) == "카테고리 분류":
                for link in dl.select("dd a"):
                    text = link.get_text(strip=True)
                    if text:
                        category_set.add(text)
        category = ", ".join(sorted(category_set))

        def extract_text_with_newlines(selector):
            elem = soup.select_one(selector)
            if not elem:
                return "N/A"
            for br in elem.select("br"):
                br.replace_with("\n")
            return elem.text.strip()

        introduce = extract_text_with_newlines("#infoset_introduce textarea.txtContentText")
        index = extract_text_with_newlines("#infoset_toc textarea.txtContentText")
        pub_review = extract_text_with_newlines("#infoset_pubReivew textarea.txtContentText")

        return {
            "ISBN": book_isbn,
            "TITLE": title,
            "AUTHOR": author,
            "PUBLISHER": publisher,
            "PUBLISHED_DATE": published_date,
            "PAGE": page,
            "BOOK_IMAGE": image_url,
            "CATEGORY": category,
            "INTRO": introduce,
            "CONTENTS": index,
            "PUBLISHER_REVIEW": pub_review
        }

    except Exception as e:
        print(f"[ERROR] ISBN {book_isbn} 정보 추출 오류: {e}")
        return None


def save_data(crawled_data, output_filename):
    try:
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        pd.DataFrame(crawled_data).to_csv(output_filename, index=False, encoding="utf-8")
        print(f"[SAVE] {output_filename} 저장 완료.")
    except Exception as e:
        print(f"[ERROR] CSV 저장 실패: {e}")


def main():
    input_filename = "NL_BO_BOOK_PUB_202402-1"
    input_path = f"data/bookdata_steadyseller/bookdata_yes24_steadyseller_isbn.csv"
    output_path = f"data/bookdata_steadyseller/bookdata_steadyseller.csv"

    # 입력 CSV 읽기
    isbn_df = read_csv_subset(input_path)
    if isbn_df.empty:
        print("[ERROR] ISBN 목록이 비어있습니다.")
        sys.exit(1)

    full_isbn_list = list(isbn_df["ISBN_THIRTEEN_NO"].dropna())

    # 이미 처리된 ISBN(STATUS가 SUCCESS 또는 FAILED인 것) 읽기
    already_processed_isbns = set()
    crawled_data = []
    if os.path.exists(output_path):
        df_existing = pd.read_csv(output_path)
        if "STATUS" in df_existing.columns:
            already_processed_isbns = set(df_existing.loc[df_existing["STATUS"].isin(["SUCCESS", "FAILED"]), "ISBN"].astype(str))
        else:
            already_processed_isbns = set(df_existing["ISBN"].astype(str))
        crawled_data = df_existing.to_dict("records")

    # 처리되지 않은 ISBN만 선택
    remaining_isbn_list = [isbn for isbn in full_isbn_list if str(isbn) not in already_processed_isbns]
    print(f"[INFO] 남은 ISBN 수: {len(remaining_isbn_list)}")

    def process_isbn(isbn):
        try:
            book_url = get_book_page_url(isbn)
            if not book_url:
                print(f"[WARN] ISBN {isbn}: 도서 URL 없음.")
                return {"ISBN": isbn, "STATUS": "FAILED"}
            book_info = get_book_info(book_url, isbn)
            if not book_info:
                print(f"[WARN] ISBN {isbn}: 정보 파싱 실패.")
                return {"ISBN": isbn, "STATUS": "FAILED"}
            book_info["STATUS"] = "SUCCESS"
            return book_info
        except Exception as e:
            print(f"[ERROR] ISBN {isbn} 처리 중 예외: {e}")
            return {"ISBN": isbn, "STATUS": "FAILED"}

    try:
        batch_size = 100
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_isbn, isbn): isbn for isbn in remaining_isbn_list}

            for idx, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                if result:
                    crawled_data.append(result)
                    if result.get("STATUS") == "SUCCESS":
                        print(f"[INFO] [{idx}/{len(remaining_isbn_list)}] ISBN {result.get('ISBN')} 크롤링 완료")
                if idx % batch_size == 0:
                    print(f"[INFO] [{idx}/{len(remaining_isbn_list)}]개 완료. 중간 저장 중...")
                    # 중간 저장 시에는 STATUS 컬럼 그대로 저장
                    save_data(crawled_data, output_path)
    except Exception as e:
        print(f"[ERROR] 병렬 크롤링 중단: {e}")
        save_data(crawled_data, output_path)
        sys.exit(1)

    # 최종 저장 전: FAILED인 행 제거 및 STATUS 컬럼 제거
    df_all = pd.DataFrame(crawled_data)
    df_success = df_all[df_all["STATUS"] == "SUCCESS"].copy()
    if "STATUS" in df_success.columns:
        df_success.drop("STATUS", axis=1, inplace=True)
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_success.to_csv(output_path, index=False, encoding="utf-8")
        print(f"[FINAL SAVE] 최종 저장 완료. (FAILED 행 제거, STATUS 컬럼 삭제됨)")
    except Exception as e:
        print(f"[ERROR] 최종 CSV 저장 실패: {e}")

    print("[SUCCESS] 전체 크롤링 완료!")


if __name__ == "__main__":
    main()
