from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# .env에서 사용자 인증 정보 불러오기
elasticsearch_host = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
elasticsearch_username = os.getenv("ELASTICSEARCH_USERNAME", "elastic")
elasticsearch_password = os.getenv("ELASTICSEARCH_PASSWORD", "1234")

# Elasticsearch 연결 (사용자 인증 포함)
es = Elasticsearch(
    elasticsearch_host,
    http_auth=(elasticsearch_username, elasticsearch_password)
)

# Elasticsearch 서버 정보 확인
try:
    info = es.info()
    print("✅ 연결 성공! 서버 정보:")
    print(info)
except Exception as e:
    print("❌ 예외 발생:", e)
