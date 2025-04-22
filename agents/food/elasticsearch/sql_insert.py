import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# csv_path = "전국통합식품영양성분정보_가공식품_표준데이터 (1).csv"
csv_path = "전국통합식품영양성분정보_음식_표준데이터.csv"

conn_info = {
    "host": "3.37.8.185",
    "port": 5433,
    "dbname": "gym",
    "user": "postgres",
    "password": "1234"
}

df = pd.read_csv(csv_path, sep=",", encoding="cp949")
df.columns = [col.strip().replace('\ufeff', '') for col in df.columns]

df = df[["식품명", "에너지(kcal)", "단백질(g)", "지방(g)", "탄수화물(g)"]]
df.columns = ["name", "calories", "protein", "fat", "carbs"]
df = df.dropna()

df["calories"] = pd.to_numeric(df["calories"], errors="coerce")
df["protein"] = pd.to_numeric(df["protein"], errors="coerce")
df["fat"] = pd.to_numeric(df["fat"], errors="coerce")
df["carbs"] = pd.to_numeric(df["carbs"], errors="coerce")
df = df.dropna()

insert_query = """
    INSERT INTO food_nutrition (
        name, calories, protein, fat, carbs,
        is_deleted
    )
    VALUES %s
    ON CONFLICT (name) DO NOTHING
"""

records = [
    (
        row.name, row.calories, row.protein, row.fat, row.carbs,
        False  # 또는 0
    )
    for row in df.itertuples(index=False)
]

try:
    conn = psycopg2.connect(**conn_info)
    cur = conn.cursor()
    execute_values(cur, insert_query, records)
    conn.commit()
    print(f"✅ 총 {len(records)}건이 food_nutrition 테이블에 성공적으로 삽입되었습니다.")
except Exception as e:
    print("❌ DB 오류 발생:", e)
finally:
    if conn:
        cur.close()
        conn.close()
