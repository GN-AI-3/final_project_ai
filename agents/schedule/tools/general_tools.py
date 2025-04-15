from langchain.agents import tool
from typing import Dict, Any, List
from ..core.database import db

@tool
def get_schema():
    """데이터베이스 스키마 정보를 반환합니다."""
    return db.get_table_info()

@tool
def run_query(query: str) -> str:
    """SQL 쿼리를 실행하고 결과를 반환합니다."""
    try:
        result = db.run(query)
        if not result or result.strip() == "":
            return "데이터가 없습니다."
        return result
    except Exception as e:
        return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}" 