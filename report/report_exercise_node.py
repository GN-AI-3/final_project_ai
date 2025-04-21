from dotenv import load_dotenv
import os
import psycopg2
from langchain_openai import ChatOpenAI
from report.report_model import reportState
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from report.report_prompt import REPORT_EXERCISE_PROMPT
from langchain.agents import create_tool_calling_agent, AgentExecutor
import requests
import json

load_dotenv()

BACKEND_URL = os.getenv("EC2_BACKEND_URL")

DB_CONFIG = {
    "dbname": os.getenv("DB_DB"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

def select_workout_log(pt_contract_id: int) -> str:
    """
    exercise_record 테이블에서 운동 기록을 조회하는 tool.
    """

    query = """
        SELECT er.date, er.memo_data, er.record_data, e.name AS exercise_name
        FROM exercise_record er
        JOIN exercise e ON er.exercise_id = e.id
        WHERE er.member_id = (
            SELECT member_id
            FROM pt_contract
            WHERE id = %s
        )
        ORDER BY er.date DESC
        LIMIT 50;
    """
    
    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def select_pt_log(pt_contract_id: int) -> str:
    """
    pt_log_exercise 테이블에서 PT 일지를 조회하는 tool.
    """

    query = """
        SELECT
            e.name AS exercise_name,
            ple.feedback,
            ple.reps,
            ple.sets,
            ple.weight,
            ps.start_time
        FROM pt_log_exercise ple
        JOIN pt_log pl ON ple.pt_log_id = pl.id
        JOIN pt_schedule ps ON pl.pt_schedule_id = ps.id
        JOIN exercise e ON ple.exercise_id = e.id
        WHERE ps.id IN (
            SELECT id
            FROM pt_schedule
            WHERE pt_contract_id = %s
            AND start_time < NOW()
            ORDER BY start_time DESC
            LIMIT 3
        )
        ORDER BY ps.start_time DESC;
    """
    
    params = (pt_contract_id,)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def process_pt_log_result(rows):
    result = []
    for row in rows:
        pt_log_entry = {
            "exercise_name": row[0],
            "feedback": row[1],
            "reps": row[2],
            "sets": row[3],
            "weight": row[4],
            "date": row[5]
        }
        result.append(pt_log_entry)
    return result

def analyze_pt_log(state: reportState, llm: ChatOpenAI):
    ptContractId = state.ptContractId

    tools = []

    pt_log_data = select_pt_log(ptContractId)
    pt_log_data = process_pt_log_result(pt_log_data)
    print("pt_log_data: ", pt_log_data)

    workout_log_data = select_workout_log(ptContractId)
    print("workout_log_data: ", workout_log_data)

    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_EXERCISE_PROMPT),
        ("user", "{pt_log_data}"),
        ("user", "{workout_log_data}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parse_errors=True,
    )

    response = agent_executor.invoke({
        "pt_log_data": pt_log_data,
        "workout_log_data": workout_log_data
    })

    print("report response: ", response["output"])
    state.exercise_report = response["output"]
    return state

def add_data(state: reportState, llm: ChatOpenAI):
    """운동 기록을 DB에 저장하는 노드"""
    try:
        # JSON 문자열 파싱
        report_data = json.loads(state.exercise_report)
        
        # API 요청 데이터 구성
        json_data = {
            "exerciseReport": report_data,  # 파싱된 JSON 객체를 직접 사용
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
    print("select_workout_log(10): ", select_workout_log(1))
    print("select_pt_log(10): ", process_pt_log_result(select_pt_log(1)))



