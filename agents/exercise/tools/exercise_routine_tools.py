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
    """웹 검색 운동 루틴 추천"""
    tavily_client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )
    results = tavily_client.search(query)
    return results

@tool
def get_user_goal(user_id: str) -> str:
    """PostgreSQL - member table에서 사용자 목표 정보 조회"""
    query = f"SELECT goal FROM member WHERE id = '{user_id}';"
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
def get_user_physical_info(user_id: str) -> str:
    """PostgreSQL - inbody table에서 사용자 신체 정보 조회"""
    query = f"SELECT tall, weight, bmi FROM inbody WHERE member_id = {user_id};"
    print("query: ", query)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()

        if result:
            row = result[0]
            tall, weight, bmi = row[0], row[1], row[2]
            return (
                f"사용자 신체 정보:\n"
                f"- 키: {tall}cm\n"
                f"- 몸무게: {weight}kg\n"
                f"- BMI: {bmi}\n"
            )
        else:
            return "사용자의 신체 정보가 없습니다"
    except Exception as e:
        return f"Database error: {str(e)}"