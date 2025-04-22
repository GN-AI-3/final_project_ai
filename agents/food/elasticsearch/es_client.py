from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

try:
    info = es.info()
    print("✅ 연결 성공! 서버 정보:")
    print(info)
except Exception as e:
    print("❌ 예외 발생:", e)
