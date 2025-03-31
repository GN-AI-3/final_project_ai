import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sklearn.preprocessing import MinMaxScaler

# CSV 파일 로드
file_path = '전국통합식품영양성분정보표준데이터.csv'
df = pd.read_csv(file_path, encoding='euc-kr')

# 데이터 1000개만 선택
df = df.head(1000).copy()

# 영양소별로 정규화하기 위한 개별 범위 설정
def normalize_nutrients(df):
    # 영양소별 최소-최대 정규화
    df['단백질(g)'] = (df['단백질(g)'] - df['단백질(g)'].min()) / (df['단백질(g)'].max() - df['단백질(g)'].min())
    df['지방(g)'] = (df['지방(g)'] - df['지방(g)'].min()) / (df['지방(g)'].max() - df['지방(g)'].min())
    df['탄수화물(g)'] = (df['탄수화물(g)'] - df['탄수화물(g)'].min()) / (df['탄수화물(g)'].max() - df['탄수화물(g)'].min())
    df['식이섬유(g)'] = (df['식이섬유(g)'] - df['식이섬유(g)'].min()) / (df['식이섬유(g)'].max() - df['식이섬유(g)'].min())
    df['칼슘(mg)'] = (df['칼슘(mg)'] - df['칼슘(mg)'].min()) / (df['칼슘(mg)'].max() - df['칼슘(mg)'].min())
    df['비타민 C(mg)'] = (df['비타민 C(mg)'] - df['비타민 C(mg)'].min()) / (df['비타민 C(mg)'].max() - df['비타민 C(mg)'].min())
    df['당류(g)'] = (df['당류(g)'] - df['당류(g)'].min()) / (df['당류(g)'].max() - df['당류(g)'].min())
    df['칼륨(mg)'] = (df['칼륨(mg)'] - df['칼륨(mg)'].min()) / (df['칼륨(mg)'].max() - df['칼륨(mg)'].min())
    return df

df = normalize_nutrients(df)

# 영양소별 가중치 설정
weights = {
    '단백질(g)': 2.0,  # 중요도 높음
    '지방(g)': 1.5,     # 중요도 중간
    '탄수화물(g)': 1.5, # 중요도 중간
    '식이섬유(g)': 1.0, # 중요도 낮음
    '칼슘(mg)': 0.5,    # 중요도 낮음
    '비타민 C(mg)': 0.5, # 중요도 낮음
    '당류(g)': 1.5,     # 중요도 중간
    '칼륨(mg)': 1.0     # 중요도 낮음
}

# 임베딩 계산에 가중치 적용
def weighted_embedding(embedding, nutrients, weights):
    weighted_embedding = []
    for i, value in enumerate(nutrients):
        weight = weights.get(df.columns[i+1], 1.0)  # df.columns[1:]는 영양소 컬럼
        weighted_embedding.append(value * weight)
    return weighted_embedding

# 음식 데이터를 텍스트로 변환하는 함수
def generate_food_text(row):
    return (
        row['식품명'],
        row['식품명'],
        f"에너지 {row.get('에너지(kcal)', 0)} kcal, 단백질 {row.get('단백질(g)', 0)}g, 지방 {row.get('지방(g)', 0)}g, 탄수화물 {row.get('탄수화물(g)', 0)}g",
        f"당류 {row.get('당류(g)', 0)}g, 식이섬유 {row.get('식이섬유(g)', 0)}g, 칼슘 {row.get('칼슘(mg)', 0)}mg, 칼륨 {row.get('칼륨(mg)', 0)}mg, 나트륨 {row.get('나트륨(mg)', 0)}mg"
    )

# 데이터 변환
food_data = [generate_food_text(row) for _, row in df.iterrows()]

# 문장 임베딩 모델 로드
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

# Qdrant 클라이언트 설정
qdrant_client = QdrantClient(url="http://localhost:6333")

# 컬렉션 목록
collections = ["food_names", "food_macros"]

# 컬렉션이 존재하지 않으면 생성
for collection in collections:
    if collection not in qdrant_client.get_collections().collections:
        qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

# 배치 업로드 처리
batch_size = 100
for i in range(0, len(food_data), batch_size):
    batch = food_data[i:i+batch_size]
    batch_names, batch_name_texts, batch_macros, batch_nutritions = zip(*batch)
    
    # 임베딩 생성
    name_embeddings = model.encode(batch_name_texts).tolist()
    macro_embeddings = model.encode(batch_macros).tolist()
    nutrition_embeddings = model.encode(batch_nutritions).tolist()

    # 포인트 데이터 생성
    def create_points(embeddings, names, name_texts, macros, nutritions, start_idx):
        return [
            PointStruct(
                id=start_idx + j + 1,
                vector=embedding,
                payload={ 
                    "name": name, 
                    "name_text": name_text, 
                    "macro_text": macro_text, 
                    "nutrition_text": nutrition_text
                }
            )
            for j, (name, name_text, macro_text, nutrition_text, embedding) in enumerate(zip(
                names, name_texts, macros, nutritions, embeddings
            ))
        ]
    
    # Qdrant에 업로드
    qdrant_client.upsert(
        collection_name="food_names",
        points=create_points(name_embeddings, batch_names, batch_name_texts, batch_macros, batch_nutritions, start_idx=i)
    )
    qdrant_client.upsert(
        collection_name="food_macros",
        points=create_points(macro_embeddings, batch_names, batch_name_texts, batch_macros, batch_nutritions, start_idx=i)
    )
 

    print(f"처리된 데이터: {i + len(batch)}/{len(food_data)}")

print("데이터 임베딩 및 저장이 완료되었습니다.")
