import requests
import pandas as pd
from bs4 import BeautifulSoup
import csv
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

# Selenium 옵션 설정
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--enable-unsafe-swiftshader")
options.add_argument("--ignore-gpu-blocklist")
options.add_argument("--disable-software-rasterizer")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def read_csv_subset(filename):
    try:
        df = pd.read_csv(filename, usecols=["ISBN_THIRTEEN_NO", "KDC_NM"])

        df['KDC_NM'] = pd.to_numeric(df['KDC_NM'], errors='coerce')
        df = df[(df['KDC_NM'] >= 800) & (df['KDC_NM'] < 900)]

        df = df[['ISBN_THIRTEEN_NO']]
        df['ISBN_THIRTEEN_NO'] = pd.to_numeric(df['ISBN_THIRTEEN_NO'], errors='coerce').astype('Int64')
        df = df.drop_duplicates().dropna()

        return df
    except Exception as e:
        print(f"[ERROR] CSV 파일 읽기 실패: {e}")
        return pd.DataFrame()


def get_book_page_url(book_isbn):
    search_url = f"https://search.kyobobook.co.kr/web/search?vPstrKeyWord={book_isbn}&orderClick=LAG"
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] 검색 페이지 요청 실패: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    if soup.find("div", class_="no_data_desc"):
        print(f"[WARN] ISBN {book_isbn}: 검색 결과가 없습니다.")
        return None

    book_detail_link = soup.find("a", class_="prod_link")
    return book_detail_link["href"] if book_detail_link else None


def get_book_info(book_url, driver, book_isbn):
    if not book_url:
        return None

    try:
        driver.get(book_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "basic_info")))
    except Exception as e:
        print(f"[ERROR] 도서 정보 페이지 로딩 실패: {e}")
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    title_span = soup.find("span", class_="prod_title")
    title = title_span.text.strip() if title_span else "N/A"

    author_div = soup.select("div.author > a")
    author = ", ".join([a.text.strip() for a in author_div]) if author_div else "N/A"

    publisher_div = soup.find("div", class_="prod_info_text")
    publisher_url = publisher_div.find("a", class_="btn_publish_link")
    publisher = publisher_url.text.strip() if publisher_url else "N/A"

    img_div = soup.find("div", class_="blur_img_wrap")
    img_url = img_div.find("img").get("src") if img_div and img_div.find("img") else "N/A"

    category_tags = soup.find_all(class_="intro_category_link")
    categories = [tag.get_text(strip=True) for tag in category_tags] if category_tags else []
    category = list(set([item for category in categories for item in category.split("/")])) if categories else ["N/A"]

    intro_tag = soup.find("div", class_="intro_bottom")
    intro_list = intro_tag.find_all("div", class_="info_text") if intro_tag else []
    intro = ''.join([intro.text.strip() for intro in intro_list]) if intro_list else "N/A"

    contents_div = soup.find("div", class_="book_contents")
    contents_li = contents_div.find("li", class_="book_contents_item") if contents_div else None
    contents = contents_li.text.strip() if contents_li else "N/A"

    publish_review_div = soup.find("div", class_="book_publish_review")
    publish_review_p = publish_review_div.find("p", class_="info_text") if publish_review_div else None
    publish_review = publish_review_p.text.strip() if publish_review_p else "N/A"

    published_date = ""
    page_num = ""
    basic_info_div = soup.find("div", class_="basic_info")
    if basic_info_div:
        for tr in basic_info_div.find_all("tr"):
            th = tr.find("th")
            if th and th.text.strip() == "발행(출시)일자":
                td = tr.find("td")
                if td:
                    published_date = td.text.strip().split('년')[0]
            if th and th.text.strip() == "쪽수":
                td = tr.find("td")
                if td:
                    page_num = td.text.strip()[:-1]
                break

    print(f"[INFO] 크롤링 완료: {title}")

    return {
        "ISBN": book_isbn,
        "TITLE": title,
        "AUTHOR": author,
        "PUBLISHER": publisher,
        "BOOK_IMAGE": img_url,
        "CATEGORY": category,
        "INTRO": intro,
        "CONTENTS": contents,
        "PUBLISHER_REVIEW": publish_review,
        "PUBLISHED_DATE": published_date,
        "PAGE": page_num
    }


def save_data(crawled_data, output_filename):
    crawled_df = pd.DataFrame(crawled_data)
    try:
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        crawled_df.to_csv(output_filename, index=False, encoding="utf-8")
        print(f"[SAVE] 데이터가 {output_filename}에 저장되었습니다!")
    except Exception as e:
        print(f"[ERROR] 병합된 CSV 파일 저장 실패: {e}")

def main():

    input_filename = "NL_BO_BOOK_PUB_202402-1"
    input_path = f"bookdata_raw/page_1/{input_filename}.csv"
    output_path = f"bookdata_crawled/page_1/{input_filename}_crawled.csv"

    isbn_df = read_csv_subset(input_path)
    if isbn_df.empty:
        print("[ERROR] ISBN 목록이 비어있습니다.")
        sys.exit(1)

    full_isbn_list = list(isbn_df["ISBN_THIRTEEN_NO"])
    crawled_data = []
    last_crawled_isbn = None

    if os.path.exists(output_path):
        try:
            previous_df = pd.read_csv(output_path)
            crawled_data = previous_df.to_dict("records")
            if not previous_df.empty:
                last_crawled_isbn = previous_df["ISBN"].dropna().iloc[-1]
                print(f"[INFO] 마지막으로 크롤링된 ISBN: {last_crawled_isbn}")
        except Exception as e:
            print(f"[ERROR] 기존 기록 불러오기 실패: {e}")

    # ✅ 문제 해결된 부분
    if pd.notna(last_crawled_isbn):
        try:
            last_crawled_isbn_int = int(last_crawled_isbn)
            if last_crawled_isbn_int in full_isbn_list:
                last_index = full_isbn_list.index(last_crawled_isbn_int)
                full_isbn_list = full_isbn_list[last_index + 1:]
        except Exception as e:
            print(f"[WARN] last_crawled_isbn 처리 중 오류 발생: {e}")

    if not full_isbn_list:
        print("[INFO] 모든 ISBN에 대해 크롤링이 완료되었습니다.")
        sys.exit(0)

    print(f"[INFO] 남은 ISBN 개수: {len(full_isbn_list)}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        for idx, isbn in enumerate(full_isbn_list, start=1):
            print(f"[INFO] {idx}/{len(full_isbn_list)} 번째 ISBN 처리 중: {isbn}")

            book_url = get_book_page_url(isbn)
            if book_url:
                book_info = get_book_info(book_url, driver, isbn)
                if book_info is None:
                    print(f"[ERROR] ISBN {isbn} 크롤링 실패. 건너뜀.")
                    continue
                else:
                    crawled_data.append(book_info)
            else:
                print(f"[WARN] ISBN {isbn}에 대한 도서 URL을 찾지 못했습니다.")

            if idx % 10 == 0:
                print(f"[INFO] {idx}번째 항목까지 중간 저장합니다.")
                save_data(crawled_data, output_path)

    except Exception as e:
        print(f"[ERROR] 크롤링 중 예외 발생: {e}. 데이터 저장 후 종료합니다.")
        save_data(crawled_data, output_path)
        driver.quit()
        sys.exit(1)

    driver.quit()
    save_data(crawled_data, output_path)
    print("[SUCCESS] 전체 크롤링 및 데이터 저장 완료!")

if __name__ == "__main__":
    main()
