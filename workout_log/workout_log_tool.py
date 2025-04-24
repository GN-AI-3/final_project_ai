import requests
import json
from dotenv import load_dotenv
import os
import psycopg2
import traceback

load_dotenv()

# 환경 변수에서 백엔드 URL 가져오기 - 모듈 상단에 한 번만 정의
BACKEND_URL = os.getenv("EC2_BACKEND_URL")

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}
    
def is_workout_log_exist(data: dict | str) -> str:
    """
    exercise_record 테이블에 해당 운동 기록이 존재하는지 확인하는 tool.
    다음 정보를 JSON 형식으로 구성하여 호출해야 한다:
    - memberId: 사용자 고유 ID (숫자)
    - exerciseId: 수행한 운동의 ID (숫자, 사전에 운동명을 검색해서 매핑해야 함, **null이 오면 안됨**)
    - date: 운동이 수행된 날짜와 시간 (ISO 8601 형식, 예: '2025-04-16T05:44:27.333Z', **null이 오면 안됨**)
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"

    memberId = data.get("memberId")
    exerciseId = data.get("exerciseId")
    date = data.get("date")

    query = """
        SELECT id FROM exercise_record
        WHERE member_id = %s AND exercise_id = %s AND date = %s
        LIMIT 1
    """

    params = (memberId, exerciseId, date)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return rows[0][0] if rows else None

def add_workout_log(data: dict | str) -> str:
    """
    새로운 운동 기록을 추가하는 tool.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"
        
    url = f"{BACKEND_URL}/api/exercise_records"
    
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwaG9uZSI6IjAxMC0xMTExLTIyMjIiLCJuYW1lIjoi7J6l6re87JqwIiwiaWQiOjQsInVzZXJUeXBlIjoiTUVNQkVSIiwiZW1haWwiOiJ1c2VyMUB0ZXN0LmNvbSIsImdvYWxzIjpbIldFSUdIVF9MT1NTIl0sImlhdCI6MTc0NTM5MTQxOCwiZXhwIjozNjM3NTUxNDE4fQ.2W6hstdDHv6NuuZPM2DSGxcGeXoeDKWhbB_wFuRlARdriVIna2l84VxaWu5QPZgk",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"API 호출 중 오류 발생: {str(e)}"

def modify_workout_log(data: dict | str) -> str:
    """
    이미 존재하는 exercise_record 에 운동 기록을 수정하는 tool.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"

    url = f"{BACKEND_URL}/api/exercise_records"
    
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwaG9uZSI6IjAxMC0xMTExLTIyMjIiLCJuYW1lIjoi7J6l6re87JqwIiwiaWQiOjQsInVzZXJUeXBlIjoiTUVNQkVSIiwiZW1haWwiOiJ1c2VyMUB0ZXN0LmNvbSIsImdvYWxzIjpbIldFSUdIVF9MT1NTIl0sImlhdCI6MTc0NTM5MTQxOCwiZXhwIjozNjM3NTUxNDE4fQ.2W6hstdDHv6NuuZPM2DSGxcGeXoeDKWhbB_wFuRlARdriVIna2l84VxaWu5QPZgk",
        "Content-Type": "application/json"
    }

    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
        return f"API 호출 중 오류 발생: {str(e)}"