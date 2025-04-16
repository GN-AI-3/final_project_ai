import requests
import json
from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

def submit_workout_log(data: dict | str) -> str:
    """
    PT 운동 세션에 대한 피드백과 운동 기록을 전송하는 tool.
    """

    # 💥 여기서 str이면 dict로 파싱해주기
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"

    url = "http://localhost:8081/api/pt_logs"
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDQ3MjE4NzksImV4cCI6MTc0NTA4MTg3OX0.VSj11Lg0fU1cn_onuYmKNFE7DYRatORXYe9rR8ixAvHN4TqkgyahL67ST5Jcwdio",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"API 호출 중 오류 발생: {str(e)}"
    
def is_workout_log_exist(ptScheduleId: int) -> str:
    query = """
        SELECT id FROM pt_log
        WHERE pt_schedule_id = %s
        LIMIT 1
    """

    params = (ptScheduleId,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows[0][0] if rows else None

def add_workout_log(data: dict | str) -> str:
    """
    이미 존재하는 pt_log 에 운동 기록을 추가하는 tool.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"
        
    url = f"http://localhost:8081/api/pt_logs/{data.get('ptLogId')}/exercises"
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDQ3MjE4NzksImV4cCI6MTc0NTA4MTg3OX0.VSj11Lg0fU1cn_onuYmKNFE7DYRatORXYe9rR8ixAvHN4TqkgyahL67ST5Jcwdio",
        "Content-Type": "application/json"
    }

    json_data = data.copy()
    json_data.pop("ptLogId", None)

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"API 호출 중 오류 발생: {str(e)}"


