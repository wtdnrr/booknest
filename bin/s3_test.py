import random
import pandas as pd
from datetime import datetime, timedelta
import boto3

# ==== 설정 ====
num_logs = 2000
user_ids = list(range(1, 36))  # 유저 1~16
book_ids = list(range(1, 110001))  # 책 1~110000
action_types = [
    "rating_star_5", "rating_star_4", "rating_star_3", "rating_star_2", "rating_star_1",
    "rating_cancel_5", "rating_cancel_4", "rating_cancel_3", "rating_cancel_2", "rating_cancel_1",
    "update_rating_star_1_2", "update_rating_star_1_3", "update_rating_star_1_4", "update_rating_star_1_5",
    "update_rating_star_2_1", "update_rating_star_2_3", "update_rating_star_2_4", "update_rating_star_2_5",
    "update_rating_star_3_1", "update_rating_star_3_2", "update_rating_star_3_4", "update_rating_star_3_5",
    "update_rating_star_4_1", "update_rating_star_4_2", "update_rating_star_4_3", "update_rating_star_4_5",
    "update_rating_star_5_1", "update_rating_star_5_2", "update_rating_star_5_3", "update_rating_star_5_4",
    "add_to_bookshelf", "cancel_bookshelf", "add_to_wishlist", "cancel_wishlist",
    "click_book_detail", "click_dislike"
]

# ==== 로그 생성 ====
base_time = datetime(2025, 4, 9, 10, 0, 0)
generated_logs = []
used_books = set()

for _ in range(num_logs):
    user_id = random.choice(user_ids)
    book_id = random.randint(1, 110000)
    while book_id in used_books:
        book_id = random.randint(1, 110000)
    used_books.add(book_id)
    action_type = random.choice(action_types)
    timestamp = base_time + timedelta(seconds=random.randint(0, 3600 * 24))  # 하루 내 랜덤
    generated_logs.append({
        "user_id": user_id,
        "book_id": book_id,
        "timestamp": timestamp.isoformat(),
        "action_type": action_type
    })

df_generated = pd.DataFrame(generated_logs)

# ==== CSV 저장 ====
csv_path = "logs_250411.csv"
df_generated.to_csv(csv_path, index=False)

# ==== S3 업로드 함수 ====
def get_s3_client():
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id="",
            aws_secret_access_key="",
            region_name="ap-northeast-2"
        )
        print("[s3_utils] S3 연결 성공")
        return s3
    except Exception as e:
        print(f"[s3_utils] S3 연결 실패: {e}")
        raise

def upload_to_s3(file_path, bucket_name, s3_key):
    try:
        s3 = get_s3_client()
        s3.upload_file(file_path, bucket_name, s3_key)
        print(f"[s3_utils] S3 업로드 완료 → s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"[s3_utils] S3 업로드 실패: {e}")
        raise

# ==== 업로드 실행 ====
upload_to_s3(
    file_path=csv_path,
    bucket_name="saffybooknest",
    s3_key="logs/250411/logs_250411.csv"
)

print(f"[upload] 생성된 2000개 로그 {csv_path} → S3 업로드 완료")