from langchain.tools import tool
from tavily import TavilyClient
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT")
}

@tool
def web_search(query: str) -> str:
    """웹 검색 기반 운동 자세 추천"""
    tavily_client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )
    results = tavily_client.search(query)
    return results

@tool
def get_user_info(user_id: str) -> str:
    """PostgreSQL - member table에서 사용자 정보 조회"""
    query = f"SELECT * FROM member WHERE id = '{user_id}';"
    print("query: ", query)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return str(result)
    except Exception as e:
        return f"Database error: {str(e)}"

@tool
def get_exercise_info(exercise_name: str) -> str:
    """운동 정보 조회"""
    return "운동 정보 조회"
