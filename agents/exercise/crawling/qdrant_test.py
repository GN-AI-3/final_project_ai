from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

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

try:
    collections = qdrant_client.get_collections()
    print("Available collections:", collections)
except Exception as e:
    print(f"Error connecting to Qdrant: {e}")