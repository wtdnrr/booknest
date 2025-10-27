import os
import time
import pandas as pd
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

COOLDOWN_TIME = 4
MAX_COMPLETION_TOKENS = 300
TIMEOUT = 10
MAX_RETRIES = 5

input_path = "../data/bookdata_crawled/bookdata_crawled_top_loan.csv"
output_path = "crawled_loan_gpt.csv"
tag_list_path = "tag_list.txt"

# 태그 리스트 불러오기
def load_tag_list(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tags = [line.strip() for line in f if line.strip()]
    return tags, "\n".join(tags)

tag_candidates, raw_tag_list = load_tag_list(tag_list_path)

# 프롬프트 생성
def generate_prompt(text):
    prompt = """
    당신은 수천 권의 문학 작품을 분석해 온 베테랑 문학 평론가입니다.  
    지금부터 아래 책의 서평 또는 소개글을 기반으로, 이 책의 정체성을 가장 잘 드러내는 태그를 고르세요.

    태깅 전 반드시 다음과 같은 순서로로 사고하고 판단하세요:

    [1단계] 이 책이 다루는 중심 주제나 메시지는 무엇인가요?
    [2단계] 이야기의 분위기(예: 따뜻함, 어두움, 긴장감 등)는 어떤가요?
    [3단계] 갈등, 문제의식, 사회적 메시지가 드러나는 지점이 있다면 무엇인가요?
    [4단계] 위 분석을 종합해, 아래 제공된 태그 목록 중에서 책을 가장 정확히 표현하는 태그를 3~7개 선택하세요.

    반드시 지켜야 할 조건:
    - 태그는 아래 제공된 목록 중에서만 선택
    - 반드시 3개 이상, 7개 이하
    - 중복 없이, 쉼표(,)로 구분된 한 줄로 출력
    - 설명, 해석, 부연 설명 없이 태그만 출력
    """
    return f"{prompt}\n\n{text}\n\n{raw_tag_list}"

# 유효 태그 추출
def extract_valid_tags(text):
    raw_tags = [tag.strip() for tag in text.split(",") if tag.strip()]
    seen = set()
    return [tag for tag in raw_tags if tag in tag_candidates and not (tag in seen or seen.add(tag))]

# 결과 저장
def save_result(isbn, tag_str):
    df_row = pd.DataFrame([{"ISBN": isbn, "TAG": tag_str}])
    write_header = not os.path.exists(output_path) or os.path.getsize(output_path) == 0
    df_row.to_csv(output_path, mode="a", header=write_header, index=False, encoding="utf-8-sig")

# 단일 태스크 처리
async def process_task(client, isbn, title, review, intro, processed_isbns, semaphore, counter):
    isbn = str(isbn).strip()
    if isbn in processed_isbns:
        return

    input_text = review if len(review.strip()) > 100 else intro
    if not input_text:
        return

    prompt = generate_prompt(input_text)

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model='gpt-4.1-mini',
                    messages=[
                        {"role": "system", "content": "문학 전문가로서 한국어로 답하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=MAX_COMPLETION_TOKENS,
                    timeout=TIMEOUT
                )
                content = response.choices[0].message.content.strip()
                tags = extract_valid_tags(content)

                tag_str = ", ".join(tags) if 3 <= len(tags) <= 7 else "N/A"
                save_result(isbn, tag_str)
                break
            except Exception as e:
                print(f"[에러 - {title}] 시도 {attempt+1}: {e}")
                await asyncio.sleep(2)

    # 진행률 + 태그 출력
    counter["done"] += 1
    print(f"[진행률] {counter['done']:,}/{counter['total']:,} 처리됨 → ISBN: {isbn} / 태그: {tag_str}")

# 메인 함수
async def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    client = AsyncOpenAI(
        base_url="https://gms.p.ssafy.io/gmsapi/api.openai.com/v1",
        api_key=api_key,
    )

    try:
        df = pd.read_csv(input_path, on_bad_lines='skip', encoding="utf-8")
    except Exception as e:
        print(f"CSV 파일 오류: {e}")
        return

    # 이미 처리된 ISBN
    processed_isbns = set()
    if os.path.exists(output_path):
        try:
            processed_df = pd.read_csv(output_path)
            processed_isbns = set(processed_df["ISBN"].astype(str).str.strip())
        except:
            pass

    tasks = []
    semaphore = asyncio.Semaphore(5)  # 동시 요청 제한
    counter = {"done": 0, "total": 0}

    # 태스크 준비
    for _, row in df.iterrows():
        isbn = str(row.get("ISBN", "")).strip()
        title = row.get("TITLE", "")
        review = str(row.get("PUBLISHER_REVIEw", "")).strip()
        intro = str(row.get("INTRO", "")).strip()

        if not isbn or isbn in processed_isbns:
            continue
        if len(review) <= 200 and len(intro) <= 200:
            continue

        counter["total"] += 1
        tasks.append(process_task(client, isbn, title, review, intro, processed_isbns, semaphore, counter))

    print(f"\n총 처리 대상: {counter['total']:,}권 (이미 처리된 {len(processed_isbns):,}권 제외)\n")

    await asyncio.gather(*tasks)

    print(f"\n📘 태그 추출 완료! 결과는 '{output_path}'에 저장되었습니다.")

# 윈도우 지원
if __name__ == "__main__":
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
