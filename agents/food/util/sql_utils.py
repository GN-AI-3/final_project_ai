# make/sql_utils.py
import psycopg2
from ..config.database_config import PG_URI

def fetch_table_data(table: str, member_id: int):
    try:
        conn = psycopg2.connect(PG_URI)
        cur = conn.cursor()

        query_map = {
            "member": """
                SELECT id AS  name, goal,  gender
                FROM member
                WHERE id = %s
            """,
            "member_diet_info": """
                SELECT allergies, food_preferences, meal_pattern, activity_level, special_requirements, food_avoidances
                FROM member_diet_info
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """,
            "inbody": """
                SELECT *
                FROM inbody
                WHERE inbody_id = %s
                ORDER BY date DESC NULLS LAST
                LIMIT 1
            """,
 
        }

        if table not in query_map:
            return {"error": f"❌ 지원되지 않는 테이블: {table}"}

        cur.execute(query_map[table], (member_id,))
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]

        cur.close()
        conn.close()

        return dict(zip(columns, row)) if row else {}

    except Exception as e:
        return {"error": str(e)}

def execute_query(query: str) -> str:
    """
    SQL 쿼리를 실행하고 결과를 반환하는 함수
    """
    try:
        conn = psycopg2.connect(PG_URI)
        cur = conn.cursor()
        cur.execute(query)
        result = cur.fetchall()
        cur.close()
        conn.close()
        
        if not result:
            return "데이터가 없습니다."
            
        return str(result)
    except Exception as e:
        return f"쿼리 실행 중 오류 발생: {str(e)}"
