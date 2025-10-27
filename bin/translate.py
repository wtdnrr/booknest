from googletrans import Translator
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast


# 🔹 번역기 초기화
translator = Translator()

def translate_text(text):
    """Google Translate API를 이용해 영어 문장을 한국어로 번역"""
    translated = translator.translate(text, src="en", dest="ko")
    return translated.text


# KoBART 모델 불러오기
model = BartForConditionalGeneration.from_pretrained("gogamza/kobart-base-v1")
tokenizer = PreTrainedTokenizerFast.from_pretrained("gogamza/kobart-base-v1")

def refine_translation(text):
    """KoBART를 사용해 번역된 문장을 소설 문체로 변환"""
    input_ids = tokenizer(text, return_tensors="pt").input_ids
    outputs = model.generate(input_ids, max_length=200)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def translate_novel(file_path, output_path):
    """영어 소설 파일을 번역하고 문체를 다듬어 저장"""
    with open(file_path, "r", encoding="utf-8") as file:
        english_text = file.readlines()
    
    translated_lines = []
    
    for line in english_text:
        if line.strip():  # 빈 줄은 건너뛰기
            raw_translation = translate_text(line)
            # refined_translation = refine_translation(raw_translation)
            translated_lines.append(raw_translation)
        else:
            translated_lines.append("")  # 빈 줄 유지
    
    # 🔹 번역 결과 저장
    # with open(output_path, "w", encoding="utf-8") as file:
    #     file.write("\n".join(translated_lines))

    # print(f"✅ 번역 완료! 번역된 파일이 저장됨: {output_path}")
    print(translated_lines)

# 🔥 실행 예제 (영어 소설 → 한국어 번역)
translate_novel("english_novel.txt", "translated_novel.txt")
