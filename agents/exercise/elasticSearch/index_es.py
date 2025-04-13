from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200").options(ignore_status=400)

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

if __name__ == "__main__":
    # index_exercise(1, "벤치프레스")
    # index_exercise(2, "레그 프레스")

    result = search_exercise_by_name("벤치 퓨레스")
    for doc in result:
        print(doc["_source"])

    # create_index_with_ngram()

    # es.indices.delete(index="exercises", ignore=[400, 404])