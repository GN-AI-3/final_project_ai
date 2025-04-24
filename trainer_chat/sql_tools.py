from .prompts import time_range_to_sql_prompt
from langchain_openai import ChatOpenAI
import json
from langchain.prompts import PromptTemplate
import pytz
import datetime
from langchain.agents import tool
from .db_utils import db

@tool
def relative_time_expr_to_sql(user_input: str) -> tuple[str, str]:
    """
    사용자 입력에서 시간 조건을 추출하여 SQL 시간 조건으로 변환합니다.

    Parameters:
    - user_input: 사용자의 입력

    Returns:
    - sql_start_expr: SQL 시작 시간 조건
    - sql_end_expr: SQL 종료 시간 조건
    """
    
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
    
    return (result["sql_start_expr"], result["sql_end_expr"])


@tool
def excute_query(query: str) -> str:
    """
    SQL 쿼리를 실행하고 결과를 반환합니다.

    Parameters:
    - query: SQL 쿼리

    Returns:
    - 쿼리 결과 문자열
    """
    
    return db.run_no_throw(query)