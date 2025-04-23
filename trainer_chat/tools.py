from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import pytz
from .db_utils import db
from langchain.tools import Tool
import re
import datetime
import dateparser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from .prompts import query_check_system, query_gen_system, time_range_extraction_prompt, extract_time_expression_prompt, time_range_to_sql_prompt
import json

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

@tool
def time_expression_to_sql_tool(user_input: str) -> dict:
    """
    사용자의 자연어 입력에서 상대적 시간 표현을 추출하여 SQL 쿼리로 변환합니다.
    """
    from langchain.prompts import PromptTemplate

    prompt = PromptTemplate.from_template(time_range_to_sql_prompt)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    range_response = llm.invoke(prompt.format(
        user_input=user_input,
        current_datetime=now.isoformat(),
        user_timezone=tz.zone,
        db_engine="PostgreSQL"
    ))

    try:
        result = json.loads(range_response.content)
    except Exception as e:
        return {"error": f"LLM 응답 파싱 실패: {e}", "raw": range_response.content}
    
    

    return result

tz = pytz.timezone("Asia/Seoul")
now = datetime.datetime.now(tz)

def date_parser(expression: str) -> dict:
    from dateparser import parse
    
    TIMEZONE = "Asia/Seoul"
    
    return parse(expression, settings={
        'DATE_ORDER': 'YMD',
        'TIMEZONE': TIMEZONE,
        'TO_TIMEZONE': TIMEZONE,
        'PREFER_DAY_OF_MONTH': 'current', # current, first, last
        'PREFER_MONTH_OF_YEAR': 'current', # current, first, last
        'PREFER_DATES_FROM': 'future', # past, future, current
        'RELATIVE_BASE': now,
        'STRICT_PARSING': False,
    }, languages=['ko'])
    

def parse_relative_range(expression: str, now_iso: str) -> dict:
    """
    상대적 시간 범위 표현을 받아 절대적 시작/끝 날짜(ISO8601)와 기타 정보를 dict로 반환합니다.
    """

    import re
    import pytz
    import dateparser
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta
    from copy import deepcopy

    cleaned_expression = expression.replace(" ", "")

    # 공통 설정 - 함수 내 재사용
    TIMEZONE = "Asia/Seoul"
    LANGUAGES = ["ko"]
    BASE_SETTINGS = {
        "TIMEZONE": TIMEZONE,
        "TO_TIMEZONE": TIMEZONE,
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DATES_FROM": "future",
        "DATE_ORDER": "YMD",
    }

    # 기준 시간 설정
    tz = pytz.timezone(TIMEZONE)
    now = datetime.fromisoformat(now_iso).astimezone(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = today.weekday()

    def get_settings():
        s = deepcopy(BASE_SETTINGS)
        s["RELATIVE_BASE"] = now
        return s

    def to_range(dt: datetime) -> tuple[datetime, datetime]:
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    def to_iso(start, end):
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "expression": cleaned_expression,
            "timezone": TIMEZONE,
        }

    # 주/월 단위 처리
    if cleaned_expression in ["이번주"]:
        start = today - timedelta(days=weekday)
        end = start + timedelta(days=7)
        return to_iso(start, end)

    if cleaned_expression in ["다음주"]:
        start = today - timedelta(days=weekday) + timedelta(weeks=1)
        end = start + timedelta(days=7)
        return to_iso(start, end)

    if cleaned_expression in ["이번달"]:
        start = today.replace(day=1)
        next_month = (start + relativedelta(months=1)).replace(day=1)
        return to_iso(start, next_month)

    if cleaned_expression in ["다음달"]:
        start = (today.replace(day=1) + relativedelta(months=1))
        end = (start + relativedelta(months=1))
        return to_iso(start, end)

    # 범위 표현
    range_parts = re.split(r"\s*[~\-]\s*|\s+to\s+", cleaned_expression)
    if len(range_parts) == 2:
        settings = get_settings()
        start_dt = dateparser.parse(range_parts[0], settings=settings, languages=LANGUAGES)
        end_dt = dateparser.parse(range_parts[1], settings=settings, languages=LANGUAGES)
        if start_dt and end_dt:
            start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return to_iso(start, end)

    # 단일 표현
    parsed = dateparser.parse(cleaned_expression, settings=get_settings(), languages=LANGUAGES)
    if parsed:
        start, end = to_range(parsed)
        return to_iso(start, end)

    return {
        "error": "Error: 변환할 수 없는 시간 표현입니다.",
        "expression": expression
    }

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

query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0)

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