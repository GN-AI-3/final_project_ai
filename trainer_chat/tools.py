from typing import Literal, Optional, Sequence, Dict, Any
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent, tool
from .db_utils import db
import re
import datetime
from langchain_core.prompts import ChatPromptTemplate
from .prompts import query_gen_system, query_check_system
import json
from .sql_tools import relative_time_expr_to_sql

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

class TimeExpressionInput(BaseModel):
    user_input: str

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


@tool
def gen_pt_schedule_query(
    input: str,
    trainer_id: int,
    status: str | None = None,
    name: Optional[str] = None,
    has_pt_log: Optional[bool] = None,
    is_deducted: Optional[bool] = None
) -> Sequence[Dict[str, Any]] | str:
    """
    트레이너의 PT 일정을 조회하는 SQL 쿼리를 생성합니다.

    Parameters:
    - input: 사용자의 입력
    - trainer_id: 트레이너의 고유 ID
    - status: 쉼표로 구분된 일정 상태 문자열
        - 유효한 값:
            - 'SCHEDULED': 예약됨
            - 'COMPLETED': 완료됨
            - 'CHANGED': 변경 이력
            - 'CANCELLED': 취소됨
            - 'NO_SHOW': 미참석
    - name: 회원 이름 검색 키워드 (부분 일치 검색)
    - has_pt_log: 운동 기록 여부 (True / False)
    - is_deducted: 회차 차감 여부 (True / False)

    Returns:
    - SQL 쿼리 문자열 또는 에러 메시지
    """

    sql_start_expr, sql_end_expr = relative_time_expr_to_sql(input)
    
    try:
        # 기본 WHERE 조건
        where_clauses = [
            "ps.is_deleted = false",
            "pc.is_deleted = false",
            "m.is_deleted = false",
            "pc.status = 'ACTIVE'",
            f"pc.trainer_id = {trainer_id}",
            f"ps.start_time >= {sql_start_expr}",
            f"ps.start_time < {sql_end_expr}"
        ]

        # 상태 필터 (쉼표 분리 후 IN 절 구성)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                status_in = ", ".join(f"'{s}'" for s in statuses)
                where_clauses.append(f"ps.status IN ({status_in})")

        # 회원 이름 검색 (부분 일치)
        if name:
            where_clauses.append(f"m.name ILIKE '%{name}%'")

        # has_pt_log 조건
        if has_pt_log:
            where_clauses.append(f"ps.has_pt_log = {str(has_pt_log).lower()}")

        # is_deducted 조건
        if is_deducted:
            where_clauses.append(f"ps.is_deducted = {str(is_deducted).lower()}")

        # 최종 쿼리 조립
        where_sql = " AND ".join(where_clauses)

        query = f"""
        SELECT
            ps.id,
            ps.current_pt_count,
            pc.total_count,
            ps.start_time,
            ps.end_time,
            m.name AS member_name
        FROM pt_schedule ps
            JOIN pt_contract pc ON ps.pt_contract_id = pc.id
            JOIN member m ON pc.member_id = m.id
        WHERE {where_sql}
        ORDER BY ps.start_time;
        """

        return query

    except Exception as e:
        return f"Error while building query: {str(e)}"
