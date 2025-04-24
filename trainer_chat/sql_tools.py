from .prompts import time_range_to_sql_prompt
from langchain_openai import ChatOpenAI
import json
from langchain.prompts import PromptTemplate
import pytz
import datetime
from langchain.agents import tool

@tool
def relative_time_expr_to_sql(user_input: str) -> dict:
    """
    사용자 입력에서 시간 조건을 추출하여 SQL 시간 조건으로 변환합니다.

    Parameters:
    - user_input: 상대적 시간 표현이 포함된 자연어 입력

    Returns:
    - sql_start_expr: SQL 시작 시간 조건
        ex) DATE_TRUNC('week', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')
    - sql_end_expr: SQL 종료 시간 조건
        ex) DATE_TRUNC('week', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul') + INTERVAL '1 week
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
    
    return { "sql_start_expr": result["sql_start_expr"], "sql_end_expr": result["sql_end_expr"] }