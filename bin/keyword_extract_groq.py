# -*- coding: utf-8 -*-

import os
import time
import pandas as pd
from queue import Queue
from threading import Thread, Lock
from dotenv import load_dotenv
from groq import Groq

start_time = time.time()

# API 키 로딩
load_dotenv()
api_keys = [
    os.getenv("API_KEY_1"),
    os.getenv("API_KEY_2"),
    os.getenv("API_KEY_3"),
    os.getenv("API_KEY_4"),
]

clients = [Groq(api_key=k) for k in api_keys]

model_list = [
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-qwen-32b",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "llama-3.2-90b-vision-preview",
    "llama-3.3-70b-specdec",
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mistral-saba-24b",
    "qwen-2.5-32b",
    "qwen-2.5-coder-32b",
    "qwen-qwq-32b"
]

# 태그 목록
raw_tag_list = """판타지
SF
미스터리
스릴러
공포
로맨스
역사소설
모험
코미디
드라마
감동적인
잔잔한
긴장감 있는
우울한
유머러스한
어두운
밝고 긍정적
철학적
역동적인
몽환적인
역설적인
잔혹한
황홀한
불안감을 조성하는
사회 비판적
불평등
젠더 문제
전쟁과 평화
운명과 자유의지
도덕적 딜레마
혁명과 저항
환경과 생태
의료 및 바이오테크
외교와 정치 음모
권력과 부패
노동과 계급투쟁
이민과 정체성
문화 충돌
무정부주의
전통과 혁신
인공지능과 정보화
성장 이야기
트라우마와 치유
우정과 동료애
종교적·영적 요소
복수와 정의
정체성 탐색
내면 탐구
기억과 시간
이중성
금기와 반항
생명과 죽음
욕망과 타락
재난·서바이벌
의식의 흐름
미완의 이야기
실험적 문체
형식 파괴적
독특한 서술 방식
디스토피아
유토피아
포스트 아포칼립스
사이버펑크
다중 우주
시간 여행
초현실적 공간
미지의 영역 탐험
이세계
신화적 세계
가상 현실
기후 변화 세계"""

tag_candidates = [t.strip() for t in raw_tag_list.strip().splitlines() if t.strip()]

def generate_prompt(text):
    prompt = """
    당신은 수천 권의 문학 작품을 분석해 온 베테랑 문학 평론가입니다.  
    지금부터 아래 책의 서평 또는 소개글을 기반으로, 이 책의 정체성을 가장 잘 드러내는 태그를 고르세요.

    태깅 전 반드시 다음과 같이 사고하고 판단하세요:

    [1단계] 이 책이 다루는 중심 주제나 메시지는 무엇인가요?
    [2단계] 이야기의 분위기(예: 따뜻함, 어두움, 긴장감 등)는 어떤가요?
    [3단계] 갈등, 문제의식, 사회적 메시지가 드러나는 지점이 있다면 무엇인가요?
    [4단계] 위 분석을 종합해, 아래 제공된 태그 목록 중에서 책을 가장 정확히 표현하는 태그를 3~5개 선택하세요.

    반드시 지켜야 할 조건:
    - 태그는 아래 제공된 목록 중에서만 선택
    - 반드시 3개 이상, 5개 이하
    - 중복 없이, 쉼표(,)로 구분된 한 줄로 출력
    - 설명, 해석, 부연 설명 없이 태그만 출력
    """
    return f"{prompt}\n\n{text}\n\n{raw_tag_list}"

def extract_valid_tags(text):
    raw_tags = [tag.strip() for tag in text.split(",") if tag.strip()]
    seen = set()
    unique_valid_tags = []
    for tag in raw_tags:
        if tag in tag_candidates and tag not in seen:
            seen.add(tag)
            unique_valid_tags.append(tag)
    return unique_valid_tags

results = {}
token_cooldown = {}
all_combos = [(m, i) for m in model_list for i in range(len(clients))]
combo_index = 0
combo_lock = Lock()
processed_isbns_lock = Lock()
task_queue = Queue()

tagged_file = "steadyseller.csv"
if os.path.exists(tagged_file):
    existing_df = pd.read_csv(tagged_file)
    processed_isbns = set(existing_df["ISBN"].dropna().astype(str).tolist())
else:
    existing_df = pd.DataFrame(columns=["ISBN", "TAG"])
    processed_isbns = set()

max_retries = 5

def model_worker():
    global combo_index
    while True:
        item = task_queue.get()
        if item is None:
            break

        idx, isbn, title, review_text, intro, retry_count = item

        with processed_isbns_lock:
            if isbn in processed_isbns:
                task_queue.task_done()
                continue

        # 조건에 따라 프롬프트 입력
        if len(review_text.strip()) > 100:
            input_text = review_text
        else:
            input_text = intro

        prompt = generate_prompt(input_text)

        with combo_lock:
            combo = all_combos[combo_index % len(all_combos)]
            combo_index += 1

        model, client_idx = combo
        client = clients[client_idx]
        cooldown_key = (model, client_idx)

        now = time.time()
        last_used = token_cooldown.get(cooldown_key, 0)
        wait_time = max(0, 4 - (now - last_used))
        if wait_time > 0:
            time.sleep(wait_time)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "문학 전문가로서 한국어로 답하세요."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_completion_tokens=300,
                top_p=1,
                stream=False,
                timeout=10
            )
            token_cooldown[cooldown_key] = time.time()
            content = response.choices[0].message.content.strip()
            tags = extract_valid_tags(content)

            if len(tags) < 3:
                print(f"⚠️ [{idx+1}] {title} → 태그 부족 → 재시도 {retry_count+1}/{max_retries}")
                if retry_count + 1 < max_retries:
                    task_queue.put((idx, isbn, title, review_text, intro, retry_count+1))
                else:
                    tag_str = "오류"
                    new_row = pd.DataFrame([{"ISBN": isbn, "TAG": tag_str}])
                    write_header = not os.path.exists(tagged_file) or os.path.getsize(tagged_file) == 0
                    new_row.to_csv(tagged_file, mode="a", header=write_header, index=False, encoding="utf-8-sig")
                    with processed_isbns_lock:
                        processed_isbns.add(isbn)
                    print(f"📌 저장된 ISBN: {isbn} / 태그: 오류")
            else:
                tag_str = ", ".join(tags)
                print(f"✅ [{idx+1}] {title} → {tags} ({model}, API_KEY_{client_idx+1})")
                new_row = pd.DataFrame([{"ISBN": isbn, "TAG": tag_str}])
                write_header = not os.path.exists(tagged_file) or os.path.getsize(tagged_file) == 0
                new_row.to_csv(tagged_file, mode="a", header=write_header, index=False, encoding="utf-8-sig")
                with processed_isbns_lock:
                    processed_isbns.add(isbn)
                print(f"📌 저장된 ISBN: {isbn} / 태그: {tag_str}")

        except Exception as e:
            print(f"❌ [{idx+1}] {title} 에러: {e} (API_KEY_{client_idx+1})")
            if retry_count + 1 < max_retries:
                task_queue.put((idx, isbn, title, review_text, intro, retry_count+1))

        task_queue.task_done()

# ✅ CSV 로드 및 컬럼 소문자화
df = pd.read_csv("bookdata_steadyseller/bookdata_steadyseller.csv", on_bad_lines='skip', encoding="utf-8")
# df.columns = [col.lower() for col in df.columns]

# ✅ task_queue에 넣기 전에 intro + review가 둘 다 짧으면 제외
for idx, row in df.iterrows():
    isbn = str(row.get("ISBN", "")).strip()
    if not isbn or isbn.lower() == "nan" or isbn in processed_isbns:
        continue

    title = row.get("TITLE", "")
    review = str(row.get("PUBLISHER_REVIEw", "")).strip()
    intro = str(row.get("INTRO", "")).strip()

    if len(review) <= 50 and len(intro) <= 50:
        continue  # ✅ 둘 다 짧으면 태그 생략

    task_queue.put((idx, isbn, title, review, intro, 0))

# ✅ 쓰레드 실행
threads = []
num_threads = len(model_list) * len(clients) // 2
for _ in range(num_threads):
    t = Thread(target=model_worker)
    t.start()
    threads.append(t)

# ✅ 작업 대기
task_queue.join()
for _ in threads:
    task_queue.put(None)
for t in threads:
    t.join()

end_time = time.time()
print(f"\n✅ 서평 태그 추출 완료 → '{tagged_file}'에 저장됨!")
print(f"⏱️ 전체 소요 시간: {end_time - start_time:.2f}초")