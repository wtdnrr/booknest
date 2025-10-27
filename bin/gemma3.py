from transformers import AutoProcessor, AutoTokenizer, Gemma3ForConditionalGeneration, pipeline
import torch
from huggingface_hub import login

# Hugging Face 로그인
login("")

# 모델과 토크나이저 로드
model_name = "google/gemma-3-4b-it"  # 모델 이름 확인

tokenizer = AutoTokenizer.from_pretrained(model_name)

model = Gemma3ForConditionalGeneration.from_pretrained(
    model_name,
    torch_dtype=torch.bfloat16, 
    device_map="auto"
)

# 파이프라인 생성
pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)

# 입력 예제
messages = "can you explain about yourself?"

# 모델 실행
output = pipe(messages, max_new_tokens=200)

# 출력 확인
print(output[0]["generated_text"])
