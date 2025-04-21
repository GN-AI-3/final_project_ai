from elasticsearch import Elasticsearch
import psycopg2

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
es = Elasticsearch("http://elasticsearch:9200")
index_name = "food_nutrition_index"

# ✅ 인덱스 재생성 (자동완성 + 오타 대응 설정 포함)
def recreate_elasticsearch_index():
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    index_settings = {
        "settings": {
            "analysis": {
                "filter": {
                    "autocomplete_filter": {
                        "type": "edge_ngram",
                        "min_gram": 1,
                        "max_gram": 20
                    }
                },
                "analyzer": {
                    "autocomplete_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "autocomplete_filter"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "name": {
                    "type": "text",
                    "analyzer": "autocomplete_analyzer",
                    "search_analyzer": "standard"
                }
            }
        }
    }

    es.indices.create(index=index_name, body=index_settings)
    print("✅ Elasticsearch 인덱스 재생성 완료!")
from elasticsearch.helpers import bulk 
# ✅ 음식명 전체 동기화
# ✅ 음식명 전체 동기화 (bulk 버전)
def sync_food_names_to_elasticsearch():
    pg_cur.execute("SELECT id, name FROM food_nutrition")
    rows = pg_cur.fetchall()

    actions = [
        {
            "_index": index_name,
            "_id": id,
            "_source": {"id": id, "name": name}
        }
        for id, name in rows
    ]

    success, _ = bulk(es, actions)
    print(f"✅ 총 {success}개의 음식명이 ES에 bulk 색인 완료!")
# ✅ 검색 with 자동완성 + 오타
def search_food_with_autocorrect(query):
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

    results = es.search(index=index_name, body=body)

    if not results["hits"]["hits"]:
        print(f"❌ 검색 결과 없음: '{query}'")
        return

    top_hit = results["hits"]["hits"][0]["_source"]
    food_id = top_hit["id"]
    food_name = top_hit["name"]
    print(f"🔍 입력 '{query}' → 추천: {food_name} (ID: {food_id})")

    pg_cur.execute("SELECT * FROM food_nutrition WHERE id = %s", (food_id,))
    nutrition = pg_cur.fetchone()
    print("📊 영양정보:", nutrition)

# ✅ 실행
if __name__ == "__main__":
    recreate_elasticsearch_index()
    sync_food_names_to_elasticsearch()
    search_food_with_autocorrect("옥수수")
    search_food_with_autocorrect("옥수수")
