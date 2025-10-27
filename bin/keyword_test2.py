import pandas as pd
from groq import Groq

# Groq 클라이언트 초기화
client = Groq(api_key="")

# 키워드 추출을 위한 프롬프트와 태그 목록 정의
prompt = """

주의: 
태그를 선택할 때 하나하나 선택한 이유를 설명하는 부분은 절대 포함되면 안됩니다.
오직 태그만 쉼표(,)로 구분하여 출력해 주세요.

주어진 책 서평을 참고하여, 제가 제공한 태그 목록에서 이 책과 잘 어울리는 태그를 0~7개 로 선택해 주세요.
개수는 일관적일 필요 없이 잘 맞는 태그만 선택하면 됩니다.
적절한 태그가 하나도 없을 경우에는 빈 문자열을 출력해주세요.
"""

tag_list = """
## 태그 목록
판타지
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
기후 변화 세계
"""


# CSV 파일 읽기
input_filename = "NL_BO_BOOK_PUB_202402-1"
input_path = f"data_crawled/page_1/{input_filename}_crawled.csv"
output_path = f"data_tagged/page_1/{input_filename}_tagged.csv"
df = pd.read_csv(input_path)


def extract_keywords(review_text):
    final_prompt = prompt + review_text + tag_list
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "당신은 문학 전문가입니다. 글에서 핵심 내용을 파악하고 요약할 수 있습니다. 답변은 한국어로만 합니다."
            },
            {
                "role": "user",
                "content": final_prompt,
            }
        ],
        model="deepseek-r1-distill-llama-70b",
        temperature=0.5,
        max_completion_tokens=1024,
        top_p=1,
        stop=None,
        stream=False,
    )
    raw_output = chat_completion.choices[0].message.content.strip()
    # </think> 이후의 콤마로 구분된 부분만 추출
    if "</think>" in raw_output:
        keywords = raw_output.split("</think>")[-1].strip()
        keywords = keywords.replace("\n", "")
        return keywords
    else:
        return raw_output

# 결과를 저장할 'TAGS' 컬럼 초기화
df['TAGS'] = None

total_rows = len(df)

# 각 서평에 대해 키워드 추출 및 중간 저장 (100행마다)
for idx, row in df.iterrows():
    # PUBLISHER_REVIEW가 없으면 INTRO를 대신 사용
    review = row.get('PUBLISHER_REVIEW')
    if pd.isna(review) or review.strip() == "":
        review = row.get('INTRO')
    
    # 두 컬럼 모두 값이 없으면 TAGS에 "NA" 입력 후 다음 행으로
    if pd.isna(review) or review.strip() == "":
        ISBN = row.get('ISBN', f"Row {idx}")
        print(f"Processing {idx + 1}/{total_rows} - ISBN: {ISBN}")
        print(f"ISBN: {ISBN}: PUBLISHER_REVIEW와 INTRO 모두 없음. TAGS에 NA 입력.")
        df.at[idx, 'TAGS'] = "NA"
        continue

    # 책 식별을 위한 ISBN (없으면 row index 사용)
    ISBN = row.get('ISBN', f"Row {idx}")
    
    # 진행 상황 출력: 현재 처리중인 행 번호 / 전체 행 수
    print(f"Processing {idx + 1}/{total_rows} - ISBN: {ISBN}")
    
    try:
        tags = extract_keywords(review)
        df.at[idx, 'TAGS'] = tags
        # 추출된 태그 출력
        print(f"ISBN: {ISBN} - 추출된 태그: {tags}")
    except Exception as e:
        print(f"(ISBN: {ISBN}) 처리 중 오류 발생: {e}")
        df.at[idx, 'TAGS'] = "NA"

    # 100행마다 중간 저장
    if (idx + 1) % 10 == 0:
        df.to_csv(output_path, index=False)
        print(f"중간 저장: {idx + 1}행까지 저장 완료.")


# 최종 결과 저장
df.to_csv(output_path, index=False, encoding="utf-8-sig")
print("모든 작업 완료 및 결과 저장.")
