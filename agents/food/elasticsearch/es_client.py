from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# .env에서 사용자 인증 정보 불러오기
elasticsearch_host = os.getenv("ELASTICSEARCH_HOST")

elasticsearch_token = os.getenv("ELASTICSEARCH_SERVICEACCOUNTTOKEN")
es = Elasticsearch(
    elasticsearch_host,
    bearer_auth=elasticsearch_token
).options(ignore_status=400)


# Elasticsearch 서버 정보 확인
try:
    info = es.info()
    print("✅ 연결 성공! 서버 정보:")
    print(info)
except Exception as e:
    print("❌ 예외 발생:", e)
