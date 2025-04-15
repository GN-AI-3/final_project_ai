import requests

def submit_workout_log(data: dict) -> str:
    """
    PT 운동 세션에 대한 피드백과 운동 기록을 전송하는 tool.
    
    Args:
        data (dict): 다음 형식의 JSON 데이터
            {
              "ptScheduleId": int,
              "feedback": str,
              "injuryCheck": bool,
              "nextPlan": str,
              "exercises": [
                {
                  "exerciseId": int,
                  "sets": int,
                  "reps": int,
                  "weight": int,
                  "restTime": int,
                  "feedback": str
                }
              ]
            }

    Returns:
        str: API 응답 메시지
    """
    url = "http://localhost:8000/api/pt_logs"
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.text  # 또는 response.json() 원하면 바꿔줘!
    except requests.exceptions.RequestException as e:
        return f"API 호출 중 오류 발생: {str(e)}"