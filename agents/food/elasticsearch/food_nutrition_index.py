from elasticsearch import Elasticsearch
import psycopg2
from fastapi import FastAPI, HTTPException

app = FastAPI()

# Elasticsearch 연결
es = Elasticsearch("http://elasticsearch:9200")
# PostgreSQL 연결 (전역 변수로 관리)
pg_conn = None
pg_cur = None

# Elasticsearch 연결 (전역 변수로 관리)
es = None
index_name = "food_nutrition_index"

def connect_db():
    global pg_conn, pg_cur
    pg_conn = psycopg2.connect(
        host="3.37.8.185",
        port=5433,
        dbname="gym",
        user="postgres",
        password="1234"
    )
    pg_cur = pg_conn.cursor()

def connect_es():
    global es
    es = Elasticsearch("http://localhost:9200")

# ✅ 인덱스 재생성 (자동완성 + 오타 대응 설정 포함)
def recreate_elasticsearch_index():
    try:
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
        return {"message": "✅ Elasticsearch 인덱스 재생성 완료!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch 인덱스 재생성 실패: {str(e)}")

from elasticsearch.helpers import bulk
# ✅ 음식명 전체 동기화
# ✅ 음식명 전체 동기화 (bulk 버전)
def sync_food_names_to_elasticsearch():
    try:
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
        return {"message": f"✅ 총 {success}개의 음식명이 ES에 bulk 색인 완료!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"음식명 동기화 실패: {str(e)}")

# ✅ 인덱스 재생성 및 데이터 동기화를 한 번에 수행하는 POST 엔드포인트
@app.post("/initialize-elasticsearch")
async def initialize_elasticsearch():
    connect_es()
    connect_db()
    try:
        recreate_elasticsearch_index()
        sync_result = sync_food_names_to_elasticsearch()
        return {"recreate_index_status": "success", "sync_status": sync_result["message"]}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch 초기화 실패: {str(e)}")

# ✅ 검색 with 자동완성 + 오타 (API 엔드포인트 유지)
@app.get("/search")
async def search_food(query: str):
    # ... (기존 search_food 코드와 동일)
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
        return {"message": f"검색 결과 없음: '{query}'"}

    top_hit = results["hits"]["hits"][0]["_source"]
    food_id = top_hit["id"]
    food_name = top_hit["name"]

    pg_cur.execute("SELECT * FROM food_nutrition WHERE id = %s", (food_id,))
    nutrition = pg_cur.fetchone()

    return {
        "query": query,
        "recommendation": {"id": food_id, "name": food_name},
        "nutrition": nutrition
    }

# ✅ 서버 시작 시 데이터베이스 및 Elasticsearch 연결 (이제 초기화 API에서 연결하므로 선택 사항)
# async def startup_event():
#     print("🚀 서버 시작!")
#     # connect_db()
#     # connect_es()

# # ✅ 서버 종료 시 데이터베이스 연결 종료 (선택 사항)
# async def shutdown_event():
#     if pg_conn:
#         pg_conn.close()
#         print("🚪 PostgreSQL 연결 종료!")

# ✅ 실행 (uvicorn으로 실행해야 함)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


def initialize_elasticsearch2():
    connect_es()
    connect_db()
    try:
        recreate_elasticsearch_index()
        sync_result = sync_food_names_to_elasticsearch()
        return {"recreate_index_status": "success", "sync_status": sync_result["message"]}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch 초기화 실패: {str(e)}")

initialize_elasticsearch2()