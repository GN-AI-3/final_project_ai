from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import SearchParams
import os
from dotenv import load_dotenv
import json
from sentence_transformers import SentenceTransformer
import glob
from tqdm import tqdm
import uuid

# .env 파일에서 환경 변수 로드
load_dotenv()

# Qdrant 클라이언트 초기화
qdrant_client = QdrantClient(
    url="https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333", 
    api_key=os.getenv("QDRANT_API_KEY")
)

# API 키 확인
if not os.getenv("QDRANT_API_KEY"):
    raise ValueError("QDRANT_API_KEY environment variable is not set")

# Sentence Transformer 모델 초기화
# model = SentenceTransformer('all-MiniLM-L6-v2')
model = SentenceTransformer('all-mpnet-base-v2')

def create_exercise_collection():
    """운동 데이터를 저장할 컬렉션 생성"""
    try:
        qdrant_client.create_collection(
            collection_name="exercises",
            vectors_config=models.VectorParams(
                # size=384,  # all-MiniLM-L6-v2 모델의 임베딩 크기
                size=768,  # all-mpnet-base-v2 모델의 임베딩 크기
                distance=models.Distance.COSINE
            )
        )
        print("Collection 'exercises' created successfully")
    except Exception as e:
        print(f"Collection might already exist: {e}")

def flatten_json(y, prefix=''):
    out = []

    if isinstance(y, dict):
        for k, v in y.items():
            new_prefix = f"{prefix} {k}".strip()
            out.extend(flatten_json(v, new_prefix))
    elif isinstance(y, list):
        for i, item in enumerate(y):
            out.extend(flatten_json(item, prefix))
    else:
        out.append(f"{prefix}: {y}")

    return out

def prepare_text(data):
    flat_parts = flatten_json(data)
    return " ".join(flat_parts)

def process_json_files():
    """JSON 파일들을 처리하여 Qdrant에 저장"""
    json_dir = "data/exercise_list_json_title"
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    print(f"Found {len(json_files)} JSON files to process")
    
    for json_file in tqdm(json_files, desc="Processing JSON files"):
        try:
            # JSON 파일 읽기
            with open(json_file, 'r', encoding='utf-8') as f:
                exercise_data = json.load(f)
            
            # 운동 데이터를 텍스트로 변환
            exercise_text = prepare_text(exercise_data)

            # chunking by langchain
            # text_splitter = RecursiveCharacterTextSplitter(
            #     chunk_size=1000,
            #     chunk_overlap=200
            # )
            # chunks = text_splitter.split_text(exercise_text)
            
            # 텍스트 임베딩 생성
            embedding = model.encode(exercise_text)
            
            # Qdrant에 데이터 저장
            qdrant_client.upsert(
                collection_name="exercises",
                points=[
                    models.PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, json_file)),
                        vector=embedding.tolist(),
                        payload={
                            "exercise_name": exercise_data.get('exercise_name', ''),
                            "file_path": json_file,
                            "target_muscles": exercise_data.get("Muscles", {}).get("Target", []),
                            "content": exercise_text
                        }
                    )
                ]
            )
        
            print(f"Processed {json_file}")
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

def save():
    """메인 실행 함수"""
    try:
        # 컬렉션 생성
        create_exercise_collection()
        
        # JSON 파일 처리
        process_json_files()
        
        print("All files processed successfully")
        
    except Exception as e:
        print(f"Error in main execution: {e}")

def checkInfo():
    # print(qdrant_client.get_collection("exercises"))
    print(qdrant_client.count("exercises"))

def test():
    query_text = "Chest workouts"
    query_vector = model.encode(query_text).tolist()

    search_results = qdrant_client.search(
        collection_name="exercises",
        query_vector=query_vector,
        limit=5,  # 검색할 최대 결과 수
        search_params=SearchParams(hnsw_ef=128, exact=False)
    )

    print("검색 결과")
    for i, result in enumerate(search_results):
        print(f"{i+1}. ID: {result.id}, Score: {result.score}, Payload: {result.payload}")

if __name__ == "__main__":
    test()
    # create_exercise_collection()
    # process_json_files()