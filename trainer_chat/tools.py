from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent, tool
import pytz
from .db_utils import db
import re
import datetime
from langchain_core.prompts import ChatPromptTemplate
from .prompts import query_gen_system, query_check_system, time_range_to_sql_prompt
import json

from pydantic import BaseModel, Field
from langchain_core.tools import Tool

toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o-mini"))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

def get_clean_schema(table_name: str) -> str:
    raw_schema = db.get_table_info_no_throw(table_name.split(", "))
    clean_schema = re.sub(r"/\*.*?\*/", "", raw_schema, flags=re.DOTALL)
    return clean_schema

get_schema_tool = Tool.from_function(
    name="sql_db_schema",
    description="Return the schema for the given table name",
    func=get_clean_schema
)

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result

def time_expression_to_sql(user_input: str) -> dict:
    """
    사용자 입력에서 시간 조건을 추출하여 SQL 시간 조건으로 변환합니다.

    Parameters:
    - user_input: 사용자의 자연어 입력 전체(시간, 이벤트 등 포함)

    Returns:
    - sql_start_expr: SQL 시작 시간 조건 ex) DATE_TRUNC('week', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')
    - sql_end_expr: SQL 종료 시간 조건 ex) DATE_TRUNC('week', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul') + INTERVAL '1 week
    """
    from langchain.prompts import PromptTemplate

    tz = pytz.timezone("Asia/Seoul")
    now = datetime.datetime.now(tz)

    time_range_prompt = PromptTemplate.from_template(time_range_to_sql_prompt)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    range_response = llm.invoke(time_range_prompt.format(
        user_input=user_input,
        current_datetime=now.isoformat(),
        user_timezone=tz.zone,
        db_engine="PostgreSQL"
    ))

    try:
        result = json.loads(range_response.content)
    except Exception as e:
        return "Error: LLM 응답 파싱 실패"
    
    return { "sql_start_expr": result["sql_start_expr"], "sql_end_expr": result["sql_end_expr"] }

class TimeExpressionInput(BaseModel):
    user_input: str

time_expression_to_sql_tool = Tool.from_function(
    name="time_expression_to_sql",
    description=(
        "human 메세지를 받아서 해당 메세지에 대한 sql 쿼리를 생성한다."
        "- user_input: human 메세지 전체"
    ),
    func=time_expression_to_sql,
    args_schema=TimeExpressionInput
)

query_check_prompt = ChatPromptTemplate.from_messages([
    ("system", query_check_system), ("placeholder", "{messages}")
])
query_check = query_check_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0)

query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system), ("placeholder", "{messages}")
])

class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="The final answer to the user")

query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(
    [time_expression_to_sql_tool], 
    tool_choice="required"
)

class GetPtScheduleArgs(BaseModel):
    user_input: str = Field(..., description="자연어 입력")
    trainer_id: int = Field(..., description="트레이너 ID")


@tool
def get_pt_schedule(user_input: str, trainer_id: int) -> str:
    """
    트레이너의 PT 일정을 조회하는 함수입니다.

    Parameters:
    - user_input: 자연어 입력
    - trainer_id: 트레이너의 고유 ID

    Returns:
    - PT 일정 정보 또는 에러 메시지
    """

    query = f"""
SELECT
    ps.id,
    ps.start_time,
    ps.end_time,
    ps.status,
    m.name AS member_name
FROM pt_schedule ps
         JOIN pt_contract pc ON ps.pt_contract_id = pc.id
         JOIN member m ON pc.member_id = m.id
WHERE ps.is_deleted = false
    AND pc.status = 'ACTIVE'
    AND ps.status = 'SCHEDULED'
    AND pc.trainer_id = {trainer_id}
ORDER BY ps.start_time;
    """

    result = db.run_no_throw(query)

    print("get_pt_schedule result: ", result)

    if not result:
        return "Error: Query failed. Please rewrite your query and try again."

    return result

if __name__ == "__main__":
    test_cases = [
        # "이번주에 예정된 수업 일정 알려줘",
        # "다음주에 있는 모든 미팅을 보여줘",
        # "6월 1일부터 6월 10일까지의 내 일정 요약해줘",
        # "5월 20일부터 6월 9일까지의 내 일정 요약해줘",
        "오늘 남은 일정이 뭐야?",
        # "내일 오전에 예약된 일정이 있니?",
        # "이번달에 있는 모든 세미나 일정 알려줘",
        # "지난주에 있었던 회의 기록 보여줘",
        # "다음달 첫째주 일정 전체 알려줘",
        # "이번주 토요일에 예약된 일정이 뭐야?",
        # "어제부터 오늘까지의 일정만 정리해줘"
    ]
    for expr in test_cases:
        result = time_expression_to_sql_tool.invoke(expr)
        # print(f"입력: {expr}\n")
        # print(f"결과: {result}\n")