from dotenv import load_dotenv
import os
import psycopg2
from langchain_openai import ChatOpenAI
from report.report_model import reportState
from langchain_core.prompts import ChatPromptTemplate
from report.report_prompt import REPORT_EXERCISE_PROMPT, REPORT_INBODY_PROMPT, REPORT_MEAL_PROMPT
from report.report_tools import select_pt_log, process_pt_log_result, select_workout_log, select_inbody_data, process_inbody_data, select_meal_records, process_meal_records, select_user_goal
import requests
import json

load_dotenv()

BACKEND_URL = os.getenv("EC2_BACKEND_URL")

def analyze_pt_log(state: reportState, llm: ChatOpenAI):
    ptContractId = state.ptContractId

    pt_log_data = select_pt_log(ptContractId)
    pt_log_data = process_pt_log_result(pt_log_data)
    print("pt_log_data: ", pt_log_data)

    workout_log_data = select_workout_log(ptContractId)
    print("workout_log_data: ", workout_log_data)

    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_EXERCISE_PROMPT),
        ("user", "{pt_log_data}"),
        ("user", "{workout_log_data}")
    ])

    response = llm.invoke(prompt.format_messages(
        pt_log_data=pt_log_data,
        workout_log_data=workout_log_data
    ))
    print("report response: ", response.content)
    # JSON 문자열을 파싱하여 딕셔너리로 변환
    state.exercise_report = json.loads(response.content)
    return state

def analyze_meal_records(state: reportState, llm: ChatOpenAI):
    ptContractId = state.ptContractId

    meal_records = select_meal_records(ptContractId)
    meal_records = process_meal_records(meal_records)
    print("meal_records: ", meal_records)

    user_goal = select_user_goal(ptContractId)
    print("user_goal: ", user_goal)

    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_MEAL_PROMPT),
        ("user", "{user_goal}"),
        ("user", "{meal_records}")
    ])

    response = llm.invoke(prompt.format_messages(meal_records=meal_records, user_goal=user_goal))
    print("meal_report: ", response.content)

    state.diet_report = json.loads(response.content)
    return state

def analyze_inbody_data(state: reportState, llm: ChatOpenAI):
    ptContractId = state.ptContractId

    inbody_data = select_inbody_data(ptContractId)
    inbody_data = process_inbody_data(inbody_data)
    print("inbody_data: ", inbody_data)

    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_INBODY_PROMPT),
        ("user", "{inbody_data}")
    ])

    response = llm.invoke(prompt.format_messages(inbody_data=inbody_data))
    print("inbody_report: ", response.content)
    # JSON 문자열을 파싱하여 딕셔너리로 변환
    state.inbody_report = json.loads(response.content)
    return state

def add_data(state: reportState, llm: ChatOpenAI):
    """운동 기록을 DB에 저장하는 노드"""
    try:
        # 이미 파싱된 딕셔너리를 직접 사용
        json_data = {
            "exerciseReport": state.exercise_report,
            "dietReport": state.diet_report,
            "inbodyReport": state.inbody_report
        }

        url = f"{BACKEND_URL}/api/reports/{state.ptContractId}"
        headers = {
            "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsImNhcmVlciI6Iu2XrOyKpO2KuOugiOydtOuEiCAxMOuFhCIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoidHJhaW5lcjEiLCJpZCI6MSwidXNlclR5cGUiOiJUUkFJTkVSIiwiY2VydGlmaWNhdGlvbnMiOlsi7IOd7Zmc7Iqk7Y-s7Lig7KeA64-E7IKsIDLquIkiLCLqsbTqsJXsmrTrj5nqtIDrpqzsgqwiXSwiZW1haWwiOiJ0cmFpbmVyQGV4YW1wbGUuY29tIiwic3BlY2lhbGl0aWVzIjpbIuyytOykkeqwkOufiSIsIuq3vOugpeqwle2ZlCIsIuyekOyEuOq1kOyglSJdLCJpYXQiOjE3NDUxMzQ2MTMsImV4cCI6MzYzNzI5NDYxM30.O8fEatYrNXcyD6Jdg7lKfiGcELvgTN_-PSIGAJj3DErfXuM1SwxtnKMv9rjp9dNx",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=json_data)
        
        if response.status_code != 200:
            error_msg = f"API 요청 실패 (상태 코드: {response.status_code}): {response.text}"
            print(error_msg)
            state.response = error_msg
            return state
            
        state.response = "운동 기록 저장 완료"
        return state

    except Exception as e:
        error_msg = f"운동 기록 저장 중 오류 발생: {str(e)}"
        print(error_msg)
        state.response = error_msg
        return state

if __name__ == "__main__":
    inbody_report = analyze_inbody_data(reportState(ptContractId=10), ChatOpenAI(model="gpt-4o-mini"))
    print("inbody_report: ", inbody_report)