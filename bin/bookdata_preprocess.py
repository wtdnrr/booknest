import os
import pandas as pd
import numpy as np

# pandas 옵션 설정 (모든 열 보이도록)
pd.set_option('display.max_columns', None)


# 입력 및 출력 폴더 경로
input_folder = "bookdata_raw/page_2"
output_folder = "bookdata_processed/page_2"


# 출력 폴더가 없으면 생성
os.makedirs(output_folder, exist_ok=True)

# 입력 폴더의 모든 CSV 파일 가져오기
csv_files = [f for f in os.listdir(input_folder) if f.endswith(".csv")]


# CSV 파일 반복 처리
for file in csv_files:
    input_path = os.path.join(input_folder, file)
    output_path = os.path.join(output_folder, f"{os.path.splitext(file)[0]}_processed.csv")

    # CSV 파일 읽기
    df = pd.read_csv(input_path)

    # 데이터 구조 확인 (디버깅 용도)
    print(f"Processing {file}: Shape {df.shape}")
    df.info()

    # 사용할 열 추출
    df_extracted = df[["AUTHR_NM", "VLM_NM", "PBLICTE_YEAR", "TITLE_NM", "ISBN_THIRTEEN_NO", "KDC_NM"]]

    # ISBN이 NA거나 중복인 행 제거
    df_cleaned = df_extracted.dropna(subset=["ISBN_THIRTEEN_NO"]).drop_duplicates(subset=["ISBN_THIRTEEN_NO"])

    # VLM_NM(권명)을 제목의 마지막에 추가
    df_cleaned['TITLE_NM'] = df_cleaned.apply(
        lambda row: f"{row['TITLE_NM']} {int(row['VLM_NM'])}" if pd.notna(row['VLM_NM']) and str(row['VLM_NM']).isdigit() else row['TITLE_NM'],
        axis=1
    )

    # VLM_NM 제거
    df_cleaned.drop(columns=["VLM_NM"], inplace=True)

    # ISBN_THIRTEEN_NO 타입 변경 (변환 불가능한 값은 NaN 처리)
    df_cleaned['ISBN_THIRTEEN_NO'] = pd.to_numeric(df_cleaned['ISBN_THIRTEEN_NO'], errors='coerce').astype('Int64')

    # KDC 800번대만 필터링
    df_cleaned = df_cleaned[df_cleaned['KDC_NM'].astype(str).str.startswith('8')]

    df_final = df_cleaned[["AUTHR_NM", "PBLICTE_YEAR", "TITLE_NM", "ISBN_THIRTEEN_NO"]]

    # 처리된 데이터 저장
    df_final.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Processed file saved: {output_path}")


print("All files processed successfully")
