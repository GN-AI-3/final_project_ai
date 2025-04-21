# 1. 음식명 검색 (오타 포함)
results = es.search(index="food_nutrition_index", body={
  "query": {
    "match": {
      "name": {
        "query": "햐미밥",  # 오타 입력
        "fuzziness": "AUTO"
      }
    }
  }
})

# 2. 가장 높은 점수의 음식 id 선택
top_hit = results["hits"]["hits"][0]
food_id = top_hit["_source"]["id"]

# 3. PostgreSQL에서 해당 음식의 영양정보 가져오기
cur.execute("SELECT * FROM food_nutrition WHERE id = %s", (food_id,))
nutrition = cur.fetchone()
print(nutrition)
