import psycopg2
from langchain_community.utilities import SQLDatabase
from ..config.database_config import PG_URI

# 데이터베이스 연결
db = SQLDatabase.from_uri(PG_URI)

def execute_query(query: str) -> str:
    """SQL 쿼리를 실행하고 결과를 반환합니다.
    
    Args:
        query: 실행할 SQL 쿼리 문자열
        
    Returns:
        str: 쿼리 실행 결과 또는 에러 메시지
    """
    print("\n📄 Executing SQL Query:\n", query)
    print("================================================")
    try:
        result = db.run(query)
        if not result or result.strip() == "":
            return "데이터가 없습니다."

        return result
    except Exception as e:
        return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"