#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import pandas as pd
from threading import Lock
from dotenv import load_dotenv
from groq import Groq
from concurrent.futures import ThreadPoolExecutor, as_completed

COOLDOWN_TIME = 4
MAX_COMPLETION_TOKENS = 300
TIMEOUT = 10
MAX_RETRIES = 5

input_path = "../data/bookdata_crawled/bookdata_crawled_top_loan.csv"
output_path = "../data/bookdata_crawled/crawled_loan.csv"
tag_list_path = "tag_list.txt"

def load_tag_list(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tags = [line.strip() for line in f if line.strip()]
    return tags, "\n".join(tags)

tag_candidates, raw_tag_list = load_tag_list(tag_list_path)

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

def extract_valid_tags(text):
    raw_tags = [tag.strip() for tag in text.split(",") if tag.strip()]
    seen = set()
    unique_valid_tags = []
    for tag in raw_tags:
        if tag in tag_candidates and tag not in seen:
            seen.add(tag)
            unique_valid_tags.append(tag)
    return unique_valid_tags

class TagExtractor:
    def __init__(self, clients, models, output_path, cooldown_time, max_tokens, timeout, max_retries, total_count):
        self.clients = clients
        self.models = models
        self.output_path = output_path
        self.cooldown_time = cooldown_time
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.total_count = total_count

        self.combo_index = 0
        self.token_cooldown = {}
        self.combo_lock = Lock()
        self.processed_isbns_lock = Lock()
        self.processed_isbns = self.load_processed_isbns(output_path)
        self.remaining_isbns = set()
        self.all_combos = [(model, i) for model in self.models for i in range(len(self.clients))]

    @staticmethod
    def load_processed_isbns(file_path):
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                return set(df["ISBN"].dropna().astype(str).str.strip().tolist())
            except Exception:
                return set()
        return set()

    def save_result(self, isbn, tag_str):
        isbn = str(isbn).strip()
        with self.processed_isbns_lock:
            if isbn in self.processed_isbns:
                return  # 중복 저장 방지

        new_row = pd.DataFrame([{"ISBN": isbn, "TAG": tag_str}])
        write_header = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        new_row.to_csv(self.output_path, mode="a", header=write_header, index=False, encoding="utf-8-sig")
        
        with self.processed_isbns_lock:
            self.processed_isbns.add(isbn)
            processed = len(self.remaining_isbns & self.processed_isbns)
            total = len(self.remaining_isbns)
            progress = f"{processed:,}/{total:,}"
        print(f"[진행률] 저장됨 → ISBN: {isbn} / 태그: {tag_str} / {progress}")

    def process_task(self, idx, isbn, title, review, intro, retry_count=0):
        isbn = str(isbn).strip()
        with self.processed_isbns_lock:
            if isbn in self.processed_isbns:
                return

        input_text = review if len(review.strip()) > 100 else intro
        prompt = generate_prompt(input_text)

        with self.combo_lock:
            combo = self.all_combos[self.combo_index % len(self.all_combos)]
            self.combo_index += 1
        model, client_idx = combo
        client = self.clients[client_idx]

        cooldown_key = (model, client_idx)
        now = time.time()
        last_used = self.token_cooldown.get(cooldown_key, 0)
        wait_time = max(0, self.cooldown_time - (now - last_used))
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
                max_completion_tokens=self.max_tokens,
                top_p=1,
                stream=False,
                timeout=self.timeout
            )
            self.token_cooldown[cooldown_key] = time.time()
            content = response.choices[0].message.content.strip()
            tags = extract_valid_tags(content)

            if len(tags) < 3 or len(tags) > 7:
                if retry_count + 1 < self.max_retries:
                    self.process_task(idx, isbn, title, review, intro, retry_count + 1)
                else:
                    self.save_result(isbn, "N/A")
            else:
                tag_str = ", ".join(tags)
                self.save_result(isbn, tag_str)
        except Exception as e:
            print(f"[에러] {title} 에러: {e} (API_KEY_{client_idx+1})")
            if retry_count + 1 < self.max_retries:
                self.process_task(idx, isbn, title, review, intro, retry_count + 1)
            else:
                self.save_result(isbn, "N/A")

def main():
    start_time = time.time()
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
        "qwen-2.5-32b",
        "qwen-2.5-coder-32b",
        "qwen-qwq-32b"
    ]

    try:
        df = pd.read_csv(input_path, on_bad_lines='skip', encoding="utf-8")
    except Exception as e:
        print(f"CSV 파일 읽기 오류: {e}")
        return

    all_isbns = set(df["ISBN"].dropna().astype(str).str.strip().tolist())
    processed_isbns = TagExtractor.load_processed_isbns(output_path)
    unprocessed_isbns = all_isbns - processed_isbns
    total_unprocessed_count = len(unprocessed_isbns)

    tag_extractor = TagExtractor(
        clients=clients,
        models=model_list,
        output_path=output_path,
        cooldown_time=COOLDOWN_TIME,
        max_tokens=MAX_COMPLETION_TOKENS,
        timeout=TIMEOUT,
        max_retries=MAX_RETRIES,
        total_count=total_unprocessed_count
    )
    tag_extractor.remaining_isbns = unprocessed_isbns

    tasks = []
    max_workers = len(model_list) * len(clients) // 2
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, row in df.iterrows():
            isbn = str(row.get("ISBN", "")).strip()
            if not isbn or isbn.lower() == "nan":
                continue
            with tag_extractor.processed_isbns_lock:
                if isbn in tag_extractor.processed_isbns:
                    continue

            title = row.get("TITLE", "")
            review = str(row.get("PUBLISHER_REVIEw", "")).strip()
            intro = str(row.get("INTRO", "")).strip()
            if len(review) <= 200 and len(intro) <= 200:
                continue

            tasks.append(executor.submit(tag_extractor.process_task, idx, isbn, title, review, intro, 0))

        for future in as_completed(tasks):
            try:
                future.result()
            except Exception as e:
                print(f"작업 중 예외 발생: {e}")

    end_time = time.time()
    print(f"태그 추출 완료! 결과는 '{output_path}'에 저장되었습니다.")
    print(f"총 소요 시간: {end_time - start_time:.2f}초")

if __name__ == "__main__":
    main()
