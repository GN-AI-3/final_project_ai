from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

def index_exercise(exercise_id: int, name: str):
    doc = {
        "exercise_id": exercise_id,
        "name": name,
    }
    es.index(index="exercises", id=exercise_id, document=doc)

if __name__ == "__main__":
    index_exercise(1, "벤치프레스")
    index_exercise(2, "레그 프레스")

