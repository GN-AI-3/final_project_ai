from typing import Sequence, Dict, Any
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent, tool
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
def get_pt_schedule(user_input: str, trainer_id: int, sql_start_expr: str, sql_end_expr: str) -> Sequence[Dict[str, Any]] | str:
    """
    트레이너의 PT 일정을 조회하는 함수입니다.

    Parameters:
    - user_input: 자연어 입력
    - trainer_id: 트레이너의 고유 ID
    - sql_start_expr: SQL 시작 시간 조건
    - sql_end_expr: SQL 종료 시간 조건

    Returns:
    - 트레이너의 PT 일정 정보 또는 에러 메시지
    """

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
    WHERE ps.is_deleted = false
        AND pc.status = 'ACTIVE'
        AND ps.status = 'SCHEDULED'
        AND pc.trainer_id = {trainer_id}
        AND ps.start_time >= {sql_start_expr}
        AND ps.start_time < {sql_end_expr}
    ORDER BY ps.start_time;
    """

    print('$$ get_pt_schedule query', query)

    result = db.run_no_throw(query)

    if not result:
        return "Error: Query failed. Please rewrite your query and try again."

    return result