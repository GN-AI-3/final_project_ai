import time
import psycopg2
from elasticsearch import Elasticsearch

# PostgreSQL 연결
pg_conn = psycopg2.connect(
    host="3.37.8.185",
    port=5433,
    dbname="gym",
    user="postgres",
    password="1234"
)
pg_cur = pg_conn.cursor()

# Elasticsearch 연결
es = Elasticsearch("http://localhost:9200")
index_name = "food_nutrition_index"

# 테스트할 검색어
query = "메밀튀밥"  # (예시: 일부만 입력해도 되는 단어)

# ✅ PostgreSQL 검색
def search_postgresql(query: str):
    sql = f"SELECT id, name FROM food_nutrition WHERE name ILIKE '%{query}%' limit 10;"
    start = time.time()
    pg_cur.execute(sql)
    results = pg_cur.fetchall()
    end = time.time()
    elapsed = (end - start) * 1000  # ms 단위 변환
    return results, elapsed

# ✅ Elasticsearch 검색
def search_elasticsearch(query: str):
    body = {
        "query": {
            "bool": {
                "should": [
                    {
                        "match": {
                            "name": {
                                "query": query,
                                "fuzziness": "AUTO"
                            }
                        }
                    },
                    {
                        "match_phrase_prefix": {
                            "name": {
                                "query": query
                            }
                        }
                    }
                ]
            }
        }
    }
    start = time.time()
    results = es.search(index=index_name, body=body)
    end = time.time()
    elapsed = (end - start) * 1000  # ms 단위 변환
    return results["hits"]["hits"], elapsed

# ✅ 테스트 실행
if __name__ == "__main__":
    # PostgreSQL 테스트
    pg_results, pg_time = search_postgresql(query)
    print(f"✅ PostgreSQL 검색 결과: {len(pg_results)}개, 소요 시간: {pg_time:.2f} ms")

    # Elasticsearch 테스트
    es_results, es_time = search_elasticsearch(query)
    print(f"✅ Elasticsearch 검색 결과: {len(es_results)}개, 소요 시간: {es_time:.2f} ms")
