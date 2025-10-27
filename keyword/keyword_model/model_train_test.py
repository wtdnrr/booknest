# train.py
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from transformers import AutoTokenizer, AutoModel
from sklearn.preprocessing import MultiLabelBinarizer
import pandas as pd
import numpy as np
from tqdm import tqdm

# --------- 설정 ---------
CSV_PATH = "pipeline_1/merged_output.csv"
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
EPOCHS = 5
BATCH_SIZE = 8
MAX_LEN = 512
LEARNING_RATE = 2e-5
MODEL_SAVE_PATH = "tag_classifier.pt"

# --------- Focal Loss ---------
class FocalLoss(nn.Module):
    def __init__(self, alpha=1, gamma=2, reduction='mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        self.bce = nn.BCEWithLogitsLoss(reduction='none')

    def forward(self, inputs, targets):
        BCE_loss = self.bce(inputs, targets)
        pt = torch.exp(-BCE_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * BCE_loss
        return focal_loss.mean() if self.reduction == 'mean' else focal_loss.sum()

# --------- 데이터 준비 ---------
df = pd.read_csv(CSV_PATH)
df = df[df["TAG"].notna() & df["TAG"].str.strip().ne("")]
print(df.shape)

def select_text(row):
    review = str(row["PUBLISHER_REVIEW"])
    intro = str(row["INTRO"])
    return intro if len(review.strip()) <= 100 else review

df["text"] = df.apply(select_text, axis=1)
df["label_list"] = df["TAG"].apply(lambda x: [t.strip() for t in x.split(",") if t.strip()])

mlb = MultiLabelBinarizer(classes=TAG_LIST)
label_matrix = mlb.fit_transform(df["label_list"])

# --------- Dataset 정의 ---------
class TagDataset(Dataset):
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
        input_ids = inputs["input_ids"].squeeze(0)
        attention_mask = inputs["attention_mask"].squeeze(0)
        label = torch.FloatTensor(self.labels[idx])
        return input_ids, attention_mask, label

# --------- 모델 정의 ---------
class MultiLabelClassifier(nn.Module):
    def __init__(self, model_name, num_labels):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        return self.classifier(cls_output)

# --------- 학습 준비 ---------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
dataset = TagDataset(df["text"].tolist(), label_matrix, tokenizer, MAX_LEN)

# 검증 셋 분리
train_size = int(0.8 * len(dataset))
train_dataset, val_dataset = random_split(dataset, [train_size, len(dataset) - train_size])
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = MultiLabelClassifier(MODEL_NAME, num_labels=len(TAG_LIST)).to(device)
criterion = FocalLoss(alpha=1, gamma=2)
optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

# --------- 학습 루프 ---------
for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    for input_ids, attention_mask, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}"):
        input_ids, attention_mask, labels = input_ids.to(device), attention_mask.to(device), labels.to(device)
        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    avg_loss = total_loss / len(train_loader)
    print(f"Epoch {epoch+1} completed. Avg Loss: {avg_loss:.4f}")

# --------- 저장 ---------
torch.save(model.state_dict(), MODEL_SAVE_PATH)
print(f"모델 저장 완료: {MODEL_SAVE_PATH}")
