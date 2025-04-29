import time
from elasticsearch import Elasticsearch

# Elasticsearch 연결
es = Elasticsearch("http://localhost:9200")
index_name = "food_nutrition_index"

# ✅ 검색 함수
def search_food(food_name: str):
    es_query = {
    "query": {
        "bool": {
            "should": [
                {
                    "term": {
                        "name_compact": {
                            "value": food_name.replace(" ", ""),
                            "boost": 30
                        }
                    }
                },
                {
                    "match_phrase": {
                        "name": {
                            "query": food_name,
                            "boost": 10  # 🔥 여기에는 fuzziness 제거!
                        }
                    }
                },
                {
                    "multi_match": {
                        "query": food_name,
                        "type": "best_fields",
                        "fields": ["name^1", "name._2gram^0.2", "name._3gram^0.1"],
                        "fuzziness": "AUTO"  # ✅ 오타 허용은 여기서 처리!
                    }
                }
            ],
            "minimum_should_match": 1
        }
    }
}


    start = time.time()
    results = es.search(index=index_name, query=es_query["query"])
    end = time.time()

    hits = results["hits"]["hits"]
    elapsed = (end - start) * 1000  # ms로 변환

    return hits, elapsed

# ✅ 테스트용 케이스
test_queries = [
    "황태해장국",  # 정확 입력
    "황태해장긱",  # 오타 입력
    "황태해"  # 일부 입력 (자동완성)
]
# test_queries = [
#     "옥수수수빵",  # 정확 입력
#     "옥수수빵",  # 오타 입력
#     "옥수수"  # 일부 입력 (자동완성)
#     "황태해장국"
# ]
# ✅ 테스트 실행
if __name__ == "__main__":
    for query in test_queries:
        hits, elapsed = search_food(query)
        print(f"🔎 검색어: '{query}'")
        print(f"🔹 결과 수: {len(hits)}개")
        if hits:
            for hit in hits[:3]:  # 상위 3개만 출력
                print(f"    - {hit['_source']['name']} (score: {hit['_score']:.2f})")
        else:
            print("    - 결과 없음")
        print(f"⏱️ 소요 시간: {elapsed:.2f} ms\n")
