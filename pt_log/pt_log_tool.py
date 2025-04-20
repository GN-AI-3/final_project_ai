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

    url = f"{BACKEND_URL}/api/pt_logs"
    
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDQ3Njk0ODMsImV4cCI6MTc0NTEyOTQ4M30.ci8oWjdExXLY9EgG61sSeMmZQ4ik0nVdvKiz06TRypCSUj-pX48GDNnRL4gnseq3",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"API 호출 중 오류 발생: {str(e)}"
    
def is_workout_log_exist(ptScheduleId: int) -> str:
    """
    pt_log 테이블에 해당 운동 세션이 존재하는지 확인하는 tool.
    """
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
        
    url = f"{BACKEND_URL}/api/pt_logs/{data.get('ptLogId')}/exercises"
    
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDQ3Njk0ODMsImV4cCI6MTc0NTEyOTQ4M30.ci8oWjdExXLY9EgG61sSeMmZQ4ik0nVdvKiz06TRypCSUj-pX48GDNnRL4gnseq3",
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

def is_exercise_log_exist(data: dict | str) -> str:
    """
    pt_log_exercise 테이블에 해당 운동 기록이 존재하는지 확인하는 tool.
    """

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"

    ptLogId = data.get("ptLogId")
    exerciseId = data.get("exerciseId")

    query = """
        SELECT id FROM pt_log_exercise
        WHERE pt_log_id = %s AND exercise_id = %s
        LIMIT 1
    """

    params = (ptLogId, exerciseId)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows[0][0] if rows else None

def modify_workout_log(data: dict | str) -> str:
    """
    이미 존재하는 pt_log 에 운동 기록을 수정하는 tool.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return f"JSON 디코딩 오류: {str(e)}"

    url = f"{BACKEND_URL}/api/pt_logs/{data.get('ptLogId')}/exercises/{data.get('exerciseLogId')}"
    
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDQ3Njk0ODMsImV4cCI6MTc0NTEyOTQ4M30.ci8oWjdExXLY9EgG61sSeMmZQ4ik0nVdvKiz06TRypCSUj-pX48GDNnRL4gnseq3",
        "Content-Type": "application/json"
    }

    json_data = data.copy()
    json_data.pop("ptLogId", None)
    json_data.pop("exerciseLogId", None)

    print("json_data: ", json_data)

    try:
        response = requests.patch(url, json=json_data, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
        return f"API 호출 중 오류 발생: {str(e)}"