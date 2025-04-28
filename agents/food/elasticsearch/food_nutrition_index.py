from langchain.tools import tool
from fastapi import FastAPI, HTTPException
import os
import psycopg2
import json
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv()


app = FastAPI()

pg_conn = None
pg_cur = None

es = None
index_name = "food_nutrition_index"

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

elasticsearch_username = os.getenv("ELASTICSEARCH_USERNAME")
elasticsearch_password = os.getenv("ELASTICSEARCH_PASSWORD")

# Elasticsearch 연결 (전역 변수로 관리)
def connect_db():
    global pg_conn, pg_cur
    try:
        pg_conn = psycopg2.connect(**DB_CONFIG)
        pg_cur = pg_conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PostgreSQL 연결 실패: {str(e)}")

def connect_es():
    global es
    try:
        es = Elasticsearch(
            os.getenv("ELASTICSEARCH_HOST"),
            http_auth=(elasticsearch_username, elasticsearch_password)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch 연결 실패: {str(e)}")

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
        recreate_index_status = recreate_elasticsearch_index()
        sync_result = sync_food_names_to_elasticsearch()
        return {"recreate_index_status": "success", "sync_status": sync_result["message"]}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch 초기화 실패: {str(e)}")

# ✅ 검색 with 자동완성 + 오타 (API 엔드포인트 유지)
@app.get("/search")
async def search_food(query: str):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    print("[Standalone] Elasticsearch 인덱스 초기화 및 동기화 시작...")
    try:
        connect_es()
        connect_db()
        recreate_index_status = recreate_elasticsearch_index()
        print(recreate_index_status)
        sync_result = sync_food_names_to_elasticsearch()
        print(sync_result)
        print("[Standalone] Elasticsearch 인덱스 초기화 및 동기화 완료!")
    except Exception as e:
        print(f"[Standalone] 오류 발생: {e}")