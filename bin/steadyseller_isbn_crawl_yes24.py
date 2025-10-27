import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# 설정
ua = UserAgent()
headers = {'User-Agent': ua.random}
BASE_URL = "https://www.yes24.com"
LIST_URL_TEMPLATE = BASE_URL + "/product/category/steadyseller?pageNumber={}&pageSize=120&categoryNumber={}"
OUTPUT_CSV = "yes24_steadyseller_isbn.csv"

CATEGORY_LIST = [
    "001001025007004004",  # 예시: 고전
    "001001025007004002",
    "001001025007004001",
    "001001025007004003",
    "001001025007001"
]

# 상품이 없는 페이지인지 확인
def is_empty_page(category, page):
    url = LIST_URL_TEMPLATE.format(page, category)
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        return soup.select_one('#yesBestList > div.noData > p.txt_tit') is not None
    except Exception as e:
        print(f"[!] 페이지 확인 오류: {url} | {e}")
        return True

# 도서 링크 추출
def get_book_links(category, page):
    url = LIST_URL_TEMPLATE.format(page, category)
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        return [
            BASE_URL + a['href']
            for a in soup.select('#yesBestList li a.gd_name') if a.get('href')
        ]
    except Exception as e:
        print(f"[!] 링크 수집 오류: {url} | {e}")
        return []

# 상세 페이지에서 ISBN 추출
def extract_isbn(book_url):
    try:
        res = requests.get(book_url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for row in soup.select('#infoset_specific table tr'):
            th = row.select_one('th')
            td = row.select_one('td')
            if th and 'ISBN13' in th.text and td:
                isbn = td.text.strip()
                print(f"[✓] ISBN 추출: {isbn}")
                return {'isbn': isbn, 'url': book_url}
        print(f"[!] ISBN 없음: {book_url}")
    except Exception as e:
        print(f"[!] 상세 페이지 오류: {book_url} | {e}")
    return None

# 전체 ISBN 크롤링
def crawl_all():
    existing_df = pd.read_csv(OUTPUT_CSV) if os.path.exists(OUTPUT_CSV) else pd.DataFrame()
    existing_urls = set(existing_df['url']) if not existing_df.empty else set()

    all_links = set()
    for category in CATEGORY_LIST:
        page = 1
        while True:
            if is_empty_page(category, page):
                break
            links = get_book_links(category, page)
            all_links.update(links)
            print(f"[+] {category} | {page}페이지 | 링크 수: {len(links)}")
            page += 1
            time.sleep(0.2)

    new_links = list(all_links - existing_urls)
    print(f"[▶] 신규 수집 대상 링크 수: {len(new_links)}")

    results = []
    for url in new_links:
        result = extract_isbn(url)
        if result:
            results.append(result)
        time.sleep(0.1)

    if not results:
        print("[!] 신규 데이터 없음.")
        return

    new_df = pd.DataFrame(results)
    full_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset='isbn')
    full_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"[✅] 저장 완료: 총 {len(full_df)}건")

if __name__ == "__main__":
    crawl_all()
