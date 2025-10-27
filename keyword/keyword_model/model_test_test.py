# evaluate.py
# -*- coding: utf-8 -*-
import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, AutoModel
import pandas as pd
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import classification_report, multilabel_confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

# --------- 설정 ---------
CSV_PATH = "pipeline_1/merged_output.csv"
MODEL_PATH = "tag_classifier.pt"
MODEL_NAME = "klue/roberta-base"
TAG_LIST = [
"판타지",
"SF",
"미스터리",
"스릴러",
"공포",
"로맨스",
"역사소설",
"모험",
"코미디",
"드라마",
"감동적인",
"잔잔한",
"긴장감 있는",
"우울한",
"유머러스한",
"어두운",
"밝고 긍정적",
"철학적",
"역동적인",
"몽환적인",
"역설적인",
"잔혹한",
"황홀한",
"불안감을 조성하는",
"사회 비판적",
"불평등",
"젠더 문제",
"전쟁과 평화",
"운명과 자유의지",
"도덕적 딜레마",
"혁명과 저항",
"환경과 생태",
"의료 및 바이오테크",
"외교와 정치 음모",
"권력과 부패",
"노동과 계급투쟁",
"이민과 정체성",
"문화 충돌"
"무정부주의",
"전통과 혁신",
"인공지능과 정보화",
"성장 이야기"
"트라우마와 치유",
"우정과 동료애",
"종교적·영적 요소",
"복수와 정의",
"정체성 탐색",
"내면 탐구",
"기억과 시간",
"이중성",
"금기와 반항",
"생명과 죽음",
"욕망과 타락",
"재난·서바이벌",
"의식의 흐름",
"미완의 이야기",
"실험적 문체",
"형식 파괴적",
"독특한 서술 방식",
"디스토피아",
"유토피아",
"포스트 아포칼립스",
"사이버펑크",
"다중 우주",
"시간 여행",
"초현실적 공간",
"미지의 영역 탐험",
"이세계",
"신화적 세계",
"가상 현실",
"기후 변화 세계"
]
MAX_LEN = 512
BATCH_SIZE = 8

# --------- 데이터 전처리 ---------
df = pd.read_csv(CSV_PATH)
df = df[df["TAG"].notna() & df["TAG"].str.strip().ne("")]

def select_text(row):
    review = str(row["PUBLISHER_REVIEW"])
    intro = str(row["INTRO"])
    return intro if len(review.strip()) <= 100 else review

df["text"] = df.apply(select_text, axis=1)
df["label_list"] = df["TAG"].apply(lambda x: [t.strip() for t in x.split(",") if t.strip()])

mlb = MultiLabelBinarizer(classes=TAG_LIST)
label_matrix = mlb.fit_transform(df["label_list"])

# --------- Dataset 재정의 ---------
class TagDataset(torch.utils.data.Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        inputs = self.tokenizer(
            self.texts[idx],
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )
        return (
            inputs["input_ids"].squeeze(0),
            inputs["attention_mask"].squeeze(0),
            torch.FloatTensor(self.labels[idx]),
        )

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
dataset = TagDataset(df["text"].tolist(), label_matrix, tokenizer, MAX_LEN)
dataloader = DataLoader(dataset, batch_size=BATCH_SIZE)

# --------- 모델 불러오기 ---------
class MultiLabelClassifier(torch.nn.Module):
    def __init__(self, model_name, num_labels):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = torch.nn.Dropout(0.3)
        self.classifier = torch.nn.Linear(self.bert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        return self.classifier(cls_output)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = MultiLabelClassifier(MODEL_NAME, len(TAG_LIST)).to(device)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.eval()

# --------- 평가 함수 ---------
def evaluate_model(threshold=0.5):
    all_labels, all_preds = [], []
    with torch.no_grad():
        for input_ids, attention_mask, labels in dataloader:
            input_ids, attention_mask = input_ids.to(device), attention_mask.to(device)
            outputs = model(input_ids, attention_mask)
            probs = torch.sigmoid(outputs).cpu().numpy()
            preds = (probs > threshold).astype(int)
            all_labels.append(labels.numpy())
            all_preds.append(preds)

    y_true = np.vstack(all_labels)
    y_pred = np.vstack(all_preds)
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=TAG_LIST, zero_division=0))
    return y_true, y_pred

def print_top_probs(model, tokenizer, text, tag_list, top_k=10):
    model.eval()
    inputs = tokenizer(text, padding="max_length", truncation=True, max_length=MAX_LEN, return_tensors="pt")
    input_ids = inputs["input_ids"].to(device)
    attention_mask = inputs["attention_mask"].to(device)

    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        probs = torch.sigmoid(logits).squeeze().cpu().numpy()

    # 상위 top_k 추출
    top_indices = probs.argsort()[::-1][:top_k]
    print(f"\n📝 입력 텍스트: {text[:100]}...")
    print("🔮 상위 예측 태그 (확률):")
    for idx in top_indices:
        print(f"- {tag_list[idx]} ({probs[idx]:.2f})")

# --------- 시각화 ---------
def plot_confusion_matrix(y_true, y_pred, tag_index, tag_name):
    matrix = multilabel_confusion_matrix(y_true, y_pred)[tag_index]
    plt.figure(figsize=(4, 4))
    sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues")
    plt.title(f"Confusion Matrix for '{tag_name}'")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.show()

def plot_label_distribution(df):
    flat_tags = [t for sublist in df["label_list"] for t in sublist]
    counter = Counter(flat_tags)
    sorted_counts = pd.DataFrame(counter.items(), columns=["Tag", "Count"]).sort_values("Count", ascending=False)

    plt.figure(figsize=(12, 6))
    sns.barplot(x="Tag", y="Count", data=sorted_counts)
    plt.xticks(rotation=90)
    plt.title("Tag Distribution")
    plt.tight_layout()
    plt.show()


# --------- 실행 ---------
# y_true, y_pred = evaluate_model(threshold=0.4)
# plot_label_distribution(df)
# plot_confusion_matrix(y_true, y_pred, tag_index=2, tag_name=TAG_LIST[2])  # 예: "철학적"

example_text = """
노엄 촘스키, 움베르토 에코와 더불어
세계 최고의 지성으로 선정된 리처드 도킨스의 대표작
“인간은 이기적 유전자의 복제 욕구를 수행하는 생존 기계다”

도킨스는 이 책에서 “인간은 유전자의 꼭두각시”라고 선언한다. 인간이 “유전자에 미리 프로그램된 대로 먹고 살고 사랑하면서 자신의 유전자를 후대에 전달하는 임무를 수행하는 존재”라는 것이다. 이러한 주장은 생물학계를 비롯해 과학계를 떠들썩하게 만들었고, 이 책은 40년 동안 이어진 학계와 언론의 수많은 찬사와 논쟁 속에 25개 이상의 언어로 번역되었으며, 젊은이들이 꼭 읽어야 할 과학계의 고전으로 자리 잡았다.

이 책은 인간을 포함한 모든 생명체는 DNA 또는 유전자에 의해 창조된 ‘생존 기계’이며, 자기의 유전자를 후세에 남기려는 ‘이기적인’ 행동을 수행하는 존재라고 주장한다. 이를 연장한 개념인 ‘밈’(문화유전) 이론과 후속작 『확장된 표현형』의 선구적인 개념도 이 책에서 확인할 수 있다. 도킨스는 이런 주장을 뒷받침하기 위해서 주요 쟁점(성의 진화, 이타주의의 본질, 협동의 진화, 적응의 범위, 무리의 발생, 가족계획, 혈연선택 등)과 방대한 현대 연구 이론과 실험(게임 이론, 진화적으로 안정한 전략의 실험, 죄수의 딜레마, 박쥐 실험, 꿀벌 실험 등)을 보여 준다. 이 책이 던지는 메시지를 통해 우리는 사회생물학의 논쟁이 되었던 유전적 요인과 환경 문화적 요인 가운데 인간의 본질을 보다 더 잘 설명할 수 있는 것이 무엇인지 생각해 보게 된다.

40여 년 동안 수많은 찬사와 논쟁의 중심에 있었던 세기의 문제작
“내 책 중 한 권을 다윈에게 선물한다면 『이기적 유전자』를 선물하겠다”

다윈이 진화론을 주장한 이후로 인류는 다윈주의 또는 자연선택설과 같은 일종의 패러다임들을 접해 왔다. 실제로 다윈의 이 패러다임은 매우 중요한 영향을 미쳤고 앞으로도 그 영향력은 계속될 것이다. 이 책은 철저한 다윈주의 진화론과 자연선택을 기본 개념으로 독특한 발상과 놀라운 주장을 전개하고 있다. 도킨스는 유전자를 다음과 같은 요지로 소개한다.

“37억 년 전 스스로 복제 사본을 만드는 힘을 가진 분자가 처음으로 원시 대양에 나타났다. 이 고대 자기 복제자의 운명은 어떻게 됐을까? 그것들은 절멸하지 않고 생존 기술의 명수가 됐다. 그러나 그것들은 아주 오래전에 자유로이 뽐내고 다니는 것을 포기했다. 이제 그것들은 거대한 군체 속에 떼 지어 마치 뒤뚱거리며 걷는 로봇 안에 안전하게 들어 있다. 그것들은 원격 조종으로 외계를 교묘하게 다루고 있으며 또한 우리 모두에게도 있다. 그것들은 우리의 몸과 마음을 창조했다. 그것들을 보존하는 것이 우리의 존재를 알게 해 주는 유일한 이유다. 그것들은 유전자라는 이름을 갖고 있으며, 인간은 유전자의 생존 기계다.”

도킨스는 인간을 포함한 생명체는 DNA 또는 유전자에 의해 창조된 기계에 불과하며, 그 기계의 목적은 자신을 창조한 주인인 유전자를 보존하는 것이라고 보고 있다. 따라서 자기와 비슷한 유전자를 조금이라도 많이 지닌 생명체를 도와 유전자를 후세에 남기려는 행동은 바로 이기적 유전자에서 비롯된 것이다. 마찬가지로 인간을 포함한 생명체가 다른 생명체를 돕는 이타적 행동도 자신과 공통된 유전자를 남기기 위한 행동일 뿐이다.

이와 같은 이유에서 유전자의 세계는 비정한 경쟁, 끊임없는 이기적 이용, 그리고 속임수로 가득 차 있다. 이것은 경쟁자 사이의 공격에서뿐만 아니라 세대 간, 그리고 암수 간의 미묘한 싸움에서도 볼 수 있다. 그러므로 유전자는 유전자 자체를 유지하려는 목적 때문에 원래 이기적일 수밖에 없으며, 그러한 이기적 유전자의 자기 복제를 통해 생물의 몸을 빌려 현재에 이르게 되었다고 보는 것이다.

문화유전론 ― 밈(meme)
“우리는 유전자의 기계로 만들어졌고 밈의 기계로 자라났다”

도킨스의 주장 가운데 특히 주목할 만한 것은 유전의 영역을 생명의 본질적인 면에서 인간 문화로까지 확장한 이른바 밈(meme) 이론, 즉 문화유전론이다. 이 이론의 핵심적 개념인 밈은 도킨스가 만든 새로운 용어로서 ‘모방’을 의미한다. 유전적 진화의 단위가 유전자라면, 문화적 진화의 단위는 밈이 되는 것이다. 유전자는 하나의 생명체에서 다른 생명체로 복제되지만, 밈은 모방을 통해 한 사람의 뇌에서 다른 사람의 뇌로 복제된다. 결과적으로 밈은 유전적인 전달이 아니라 모방이라는 매개물로 전해지는 문화 요소라고 볼 수 있다. 생명체가 유전자의 자기 복제를 통해 자신의 형질을 후세에 전달하는 것처럼 밈도 자기 복제를 하여 널리 전파되고 진화한다. 그리하여 밈은 좁게는 한 사회의 유행이나 문화 전승을 가능하게 하고, 넓게는 인류의 다양하면서도 매우 다른 문화를 만들어 나가는 원동력이 된다. 도킨스가 창안한 ‘밈(meme)’이라는 단어는 1988년부터 옥스퍼드 영어사전에 등재됐을 만큼 오늘날 널리 사용되고 있으며, ‘밈학’이라는 새로운 분야도 탄생했다.

『이기적 유전자』가 던지는 인간의 본질에 대한 물음

여전히 많은 논쟁의 대상이 되고 있는 결정론적 생명관, 즉 유전자가 모든 생명 현상에 우선한다는 저자의 주장에 대해 다음과 같은 의문을 떠올릴 수 있을 것이다. 유전자의 자기 복제 및 문화유전론의 중심에 있는 인간만큼은 다른 생명체와 어떤 차별성을 갖고 있는 것이 아닐까? 다른 생물과 확연히 구분되는 문화라는 요소를 갖고 있는 인간이 과연 맹목적인 존재가 될 수 있을까? 자유 의지를 가진 인간은 유전자의 전제적 지배에 대항할 수 있지 않을까?

이 책은 이러한 의문점에 대해 여러 동물과 조류의 실제적인 실험과 이론을 바탕으로 인간도 이기적 유전자를 존속시키기 위해 프로그램된 기계에 불과한 것인지 논리적으로 살펴보고 있다. 더 나아가 생명체 복제 기술의 발달과 인간 유전자 지도의 연구로 여러 가지 질병의 정복 가능성이 높아지면서 그 어느 때보다 유전자의 영향력이 큰 비중을 차지하게 된 지금, 인간의 본질에 결정적 영향을 미치는 것이 무엇인지 곰곰이 생각해 보게 된다.

"""
print_top_probs(model, tokenizer, example_text, TAG_LIST, top_k=10)