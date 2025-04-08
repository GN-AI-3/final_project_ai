from langchain.tools import tool
from tavily import TavilyClient
import os
import psycopg2
import re
from dotenv import load_dotenv
from psycopg2 import sql
import json
from ..models.input_models import MasterSelectInput

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT")
}

TABLE_SCHEMA = {
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "description": "회원의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다. exercise_id는 exercise 테이블의 id와 연결해 운동 이름(name)을 조회해야 합니다."
    },
    "exercise": {
        "columns": ["id", "name", "exercise_type"],
        "description": "운동 목록. name은 운동명이며, exercise_type은 카테고리입니다 (예: 유산소 등)."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "profile_image", "goal"],
        "description": "회원 정보. goal은 사용자의 운동 목표입니다 (예: 벌크업, 체중 감량)."
    }
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

@tool
def get_user_exercise_record(user_id: str) -> str:
    """PostgreSQL - exercise_record table에서 사용자 운동 기록 조회"""
    query = f"SELECT * FROM exercise_record WHERE member_id = {user_id};"
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

def get_all_table_schema() -> str:
    """PostgreSQL - 사용 가능한 테이블과 컬럼 정보를 반환"""
    schema_info = []
    for table_name, table_info in TABLE_SCHEMA.items():
        schema_info.append(f"테이블: {table_name}")
        schema_info.append(f"컬럼: {', '.join(table_info['columns'])}")
        schema_info.append(f"설명: {table_info['description']}")
        schema_info.append("--------------------------------")
    return "\n".join(schema_info)

def master_select_db(table_name: str, column_name: str, value: str) -> str:
    """PostgreSQL - 사전 정의된 모든 테이블에서 테이블명, 컬럼명, 값으로 데이터 조회
    table_name, column_name, value 모두 필수입니다.
    TABLE_SCHEMA 에 정의된 테이블만 사용 가능
    TABLE_SCHEMA 에 정의된 컬럼만 사용 가능
    
    Args:
        table_name: 조회할 테이블 이름
        column_name: (선택) 조건 컬럼 이름
        value: (선택) 조건 값
        
    Returns:
        조회된 데이터의 JSON 문자열
    """
    if table_name not in TABLE_SCHEMA:
        print("table_name: ", table_name)
        return "Invalid table name"
    
    if column_name not in TABLE_SCHEMA[table_name]["columns"]:
        print("column_name: ", column_name)
        return "Invalid column name"
    
    try:
        query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name)
        )

        params = (value,)

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        result = [dict(zip(column_names, row)) for row in rows]
        cursor.close()
        conn.close()
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return f"Database error: {str(e)}"

def master_select_db_multi(
    table_name: str, 
    conditions: dict
) -> str:
    """
    PostgreSQL - 사전 정의된 테이블에서 여러 조건(column=value)으로 데이터 조회
    TABLE_SCHEMA 에 정의된 테이블과 컬럼만 사용 가능

    Args:
        table_name: 조회할 테이블 이름
        conditions: 조회 조건 (예: {"id": "1", "email": "test@gmail.com"})

    Returns:
        JSON 문자열로 된 결과
    """
    if table_name not in TABLE_SCHEMA:
        return "Invalid table name"
    
    for col in conditions.keys():
        if col not in TABLE_SCHEMA[table_name]["columns"]:
            return f"Invalid column name: {col}"

    try:
        where_clauses = [
            sql.SQL("{} = %s").format(sql.Identifier(col)) for col in conditions.keys()
        ]
        query = sql.SQL("SELECT * FROM {} WHERE {}").format(
            sql.Identifier(table_name),
            sql.SQL(" AND ").join(where_clauses)
        )

        params = tuple(conditions.values())

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        result = [dict(zip(column_names, row)) for row in rows]
        cursor.close()
        conn.close()
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return f"Database error: {str(e)}"