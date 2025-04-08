from langchain.tools import tool
from dotenv import load_dotenv
import requests
from ..models.input_models import ExerciseRecordInput

load_dotenv()

@tool
def save_exercise_record(input: ExerciseRecordInput) -> str:
    """
    운동 기록을 백엔드 서버에 저장하는 API를 호출합니다.

    Parameters:
    - member_id: 사용자 ID
    - exercise_id: 운동 ID
    - date: 운동 날짜 (예: '2025-04-08T15:30:00')
    - record_data: 운동 기록 데이터 (dict 형태, 예: {"sets": 3, "weight": 80, "reps": [10, 8, 6]})
    - memo_data: 운동 메모 데이터 (dict 형태, 예: {"comment": "오늘 컨디션 좋았음"})

    Returns:
    - 저장 성공 여부 메시지
    """

    url = "https://localhost:8081/api/exercise_records/save_exercise_record"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "memberId": input["member_id"],
        "exerciseId": input["exercise_id"],
        "date": input["date"],
        "recordData": input["record_data"],
        "memoData": input["memo_data"]
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        return "운동 기록이 성공적으로 저장되었습니다."
    else:
        return f"운동 기록 저장 실패: {response.text}"