from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

elasticsearch_host = os.getenv("ELASTICSEARCH_HOST")
elasticsearch_token = os.getenv("ELASTICSEARCH_SERVICE_ACCOUNT_TOKEN")

es = Elasticsearch(
    elasticsearch_host,
    bearer_auth=elasticsearch_token
).options(ignore_status=400)

exercise_index_name = "exercises"

def index_exercise(exercise_id: int, name: str):
    doc = {
        "exercise_id": exercise_id,
        "name": name,
        "name_compact": name.replace(" ", "")
    }
    es.index(index=exercise_index_name, id=exercise_id, document=doc)

def create_index_with_ngram():
    index_settings = {
        "settings": {
            "analysis": {
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 20,
                        "token_chars": ["letter", "digit", "whitespace"]
                    }
                },
                "analyzer": {
                    "edge_ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "edge_ngram_tokenizer",
                        "filter": ["lowercase"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        },
                        "_2gram": {
                            "type": "text",
                            "analyzer": "edge_ngram_analyzer",
                            "search_analyzer": "standard"
                        },
                        "_3gram": {
                            "type": "text",
                            "analyzer": "edge_ngram_analyzer",
                            "search_analyzer": "standard"
                        }
                    }
                },
                "name_compact": {
                    "type": "keyword"
                },
                "exercise_id": {
                    "type": "integer"
                }
            }
        }
    }

    if es.indices.exists(index=exercise_index_name):
        es.indices.delete(index=exercise_index_name, ignore=[400, 404])

    es.indices.create(index=exercise_index_name, body=index_settings)

def search_exercise_by_name(name: str):
    name_compact = name.replace(" ", "")

    res = es.search(
        index=exercise_index_name,
        query={
            "bool": {
                "should": [
                    {
                        "term": {
                            "name_compact": {
                                "value": name_compact,
                                "boost": 30  # 정확 일치 최고 가중치
                            }
                        }
                    },
                    {
                        "match_phrase": {
                            "name": {
                                "query": name,
                                "boost": 10
                            }
                        }
                    },
                    {
                        "multi_match": {
                            "query": name,
                            "type": "best_fields",
                            "fields": ["name^1", "name._2gram^0.2", "name._3gram^0.1"]
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
    )

    hits = res["hits"]["hits"]
    if not hits:
        return []

    max_score = hits[0]["_score"]
    threshold = max_score * 0.98

    return [hit for hit in hits if hit["_score"] >= threshold]

def get_all_exercises():
    """모든 운동 데이터를 인덱스 순서대로 조회"""
    res = es.search(
        index=exercise_index_name,
        query={
            "match_all": {}
        },
        sort=[
            {"exercise_id": {"order": "asc"}}
        ],
        size=1000  # 충분히 큰 수로 설정
    )
    
    return [hit["_source"] for hit in res["hits"]["hits"]]

if __name__ == "__main__":
    # index_exercise(1, "벤치프레스")
    # index_exercise(2, "레그 프레스")
    
    exercise_name = [
        "벤치프레스", "레그 프레스", "인클라인 벤치프레스", "덤벨 벤치프레스", "인클라인 덤벨프레스",
        "체스트 플라이", "펙덱 머신 플라이", "케이블 크로스오버", "데드리프트", "바벨 로우",
        "덤벨 로우", "T바 로우", "랫풀다운", "풀업", "시티드 케이블 로우",
        "스쿼트", "프론트 스쿼트", "런지", "레그 익스텐션", "레그 컬",
        "루마니안 데드리프트", "스텝업", "힙 쓰러스트", "스미스머신 스쿼트",
        "힙 어브덕션 머신", "힙 어덕션 머신", "킥백 머신", "굿모닝", "클램셸",
        "밀리터리 프레스", "덤벨 숄더프레스", "사이드 레터럴 레이즈", "프론트 레이즈",
        "리어 델트 레이즈", "업라이트 로우", "아놀드 프레스",
        "바벨 컬", "덤벨 컬", "해머 컬", "케이블 바이셉스 컬",
        "트라이셉스 푸쉬다운", "딥스", "오버헤드 트라이셉스 익스텐션", "스컬크러셔", "크런치"
        ]

    for i in range(1, 50):
        print(exercise_name[i - 1])
        index_exercise(i, exercise_name[i - 1])

    # result = search_exercise_by_name("벤치 퓨레스")
    # for doc in result:
    #     print(doc["_source"])

    # create_index_with_ngram()

    # es.indices.delete(index="exercises", ignore=[400, 404])

    DB_CONFIG = {
        "dbname": os.getenv("DB_DB"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT")
    }
    
    exercises = get_all_exercises()
    print(f"Found {len(exercises)} exercises")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        for exercise in exercises:
            if exercise['name'] not in ["벤치프레스", "레그프레스"]:
                query = """
                    INSERT INTO exercise (exercise_type, name)
                    VALUES ('대중적인 운동', %s)
                """
                params = (exercise['name'],)
                print(f"Inserting: {exercise['name']}")
                cursor.execute(query, params)
        
        conn.commit()
        print("Data inserted successfully")
        
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("PostgreSQL connection is closed")
        
        