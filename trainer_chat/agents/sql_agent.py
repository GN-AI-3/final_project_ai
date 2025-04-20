from langgraph.graph import StateGraph, END
from typing import Dict, TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import Runnable
from langchain_community.utilities import SQLDatabase
from ..utils import PG_URI, summarize_db_schema
from trainer_chat.prompts import SQL_PROMPT, INPUT_PARSER_PROMPT
from datetime import datetime, timezone, timedelta
import json
import zoneinfo

# 1. 상태 정의
class SQLAgentState(TypedDict):
    user_input: str
    intent: str
    slots: Dict[str, str]
    output_cols: str
    sql_query: str
    sql_result: str
    final_answer: str

# 2. PostgreSQL 연결
db = SQLDatabase.from_uri(PG_URI)

# 3. LLM 준비
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 사용자의 질문에서 Intent, Slot, Output 항목을 추출하는 함수
extraction_prompt = PromptTemplate.from_template(INPUT_PARSER_PROMPT)

def extract_intent_slot_output(state: SQLAgentState) -> SQLAgentState:
    # 한국 타임존 적용
    try:
        tz = zoneinfo.ZoneInfo("Asia/Seoul")
    except Exception:
        tz = timezone(timedelta(hours=9))  # zoneinfo 미지원 시 fallback
    now_kst = datetime.now(tz)
    prompt = extraction_prompt.format(
        user_input=state['user_input'],
        current_time=now_kst.strftime("%Y-%m-%d %H:%M:%S")
    )
    response = llm.invoke(prompt)

    print("$$", response.content)

    try:
        result = json.loads(response.content)
    except Exception:
        result = {"intent": "", "slots": {}, "output": ""}

    return {
        **state, 
        "intent": result['intent'], 
        "slots": result['slots']
    }

def generate_sql(state: SQLAgentState) -> SQLAgentState:
    # TODO: 질문에 따른 테이블
    schema = summarize_db_schema(db._engine, ['pt_schedule', 'pt_contract', 'member'])
    # TODO: trainer_id 바인딩
    sql_prompt = PromptTemplate.from_template(SQL_PROMPT)
    prompt = sql_prompt.format(
        schema=schema, 
        user_question=state['user_input'], 
        trainer_id=1,
        current_time=datetime.now()
    )
    # print("[LOG] SQL 프롬프트:", prompt)
    sql = llm.invoke(prompt)
    print("[LOG] 생성된 SQL 쿼리:\n", sql.content.strip())
    return {**state, "sql_query": sql.content.strip()}

# 5. SQLExecutorNode
def execute_sql(state: SQLAgentState) -> SQLAgentState:
    print("[LOG] 실행할 SQL 쿼리:", state["sql_query"])
    try:
        result = db.run(state["sql_query"])
    except Exception as e:
        result = f"[SQL ERROR] {str(e)}"
    print("[LOG] SQL 실행 결과:", result)
    return {**state, "sql_result": result}

# 6. AnswerFormatterNode
answer_prompt = PromptTemplate.from_template("""
Here is the SQL query result:

{sql_result}

Summarize this result in a friendly and clear sentence for the user.
""")

def generate_answer(state: SQLAgentState) -> SQLAgentState:
    print("[LOG] AnswerFormatter에 전달된 sql_result:", state["sql_result"])
    prompt = answer_prompt.format(sql_result=state["sql_result"])
    print("[LOG] AnswerFormatter 프롬프트:", prompt)
    answer = llm.invoke(prompt)
    print("[LOG] 최종 응답:", answer.content.strip())
    return {**state, "final_answer": answer.content.strip()}

# 7. 그래프 정의
builder = StateGraph(SQLAgentState)

builder.set_entry_point("extract_intent_slot_output")
builder.add_node("extract_intent_slot_output", extract_intent_slot_output)
# builder.add_node("generate_sql", generate_sql)
# builder.add_node("execute_sql", execute_sql)
# builder.add_node("generate_answer", generate_answer)

# builder.add_edge("generate_sql", "execute_sql")
# builder.add_edge("execute_sql", "generate_answer")
# builder.add_edge("generate_answer", END)

builder.add_edge("extract_intent_slot_output", END)


def create_sql_agent():
    return builder.compile()

if __name__ == "__main__":
    # 에이전트 생성
    app = create_sql_agent()

    # 테스트용 입력 예시 리스트
    test_inputs = [
        # "오늘 수업 있는 회원 누구야?",
        # "내일 오전에 PT 있는 회원 보여줘.",
        # "이번 주 신규 회원 첫 수업 몇 건이야?",
        "김지혜 회원의 다음 수업 언제야?"
    ]

    for user_input in test_inputs:
        print("\n==============================")
        print(f"[테스트 입력] {user_input}")
        state = {
            "user_input": user_input
        }
        final_state = app.invoke(state)
