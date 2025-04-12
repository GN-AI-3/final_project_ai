from ..tools.exercise_routine_tools import get_all_table_schema
from langchain.tools import StructuredTool
from ..models.input_models import EmptyArgs
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from ..models.state_models import RoutingState
from langchain.tools import Tool
from ..tools.exercise_routine_tools import master_select_db_multi, web_search
from ..prompts.exercise_planning_prompts import EXERCISE_PLANNING_PROMPT, EXERCISE_PLANNING_PROMPT_2, EXERCISE_PLANNING_PROMPT_3, EXERCISE_PLANNING_PROMPT_4
import json

TABLE_SCHEMA = {
    "exercise": {
        "columns": ["id", "name", "exercise_type"],
        "description": "운동 종류 목록. name은 운동명이며, exercise_type은 카테고리입니다 (예: 유산소 등)."
    },
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "foreign_keys": {
            "member_id": "member.id",
            "exercise_id": "exercise.id"
        },
        "description": "사용자의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "profile_image", "goal"],
        "description": "사용자 정보. goal은 사용자의 운동 목표입니다 (예: 벌크업, 체중 감량)."
    }
}

TOOL_DESCRIPTIONS = [
    {
        "name": "web_search",
        "description": "웹 검색을 통해 운동 루틴이나 운동에 대한 정보를 수집한다. query에는 검색어 문자열을 넣는다.",
        "input_format": {
            "query": "검색할 키워드 또는 문장 (예: '어깨 통증 원인', '등 운동 루틴')"
        }
    },
    {
        "name": "master_select_db_multi",
        "description": "PostgreSQL 데이터베이스에서 특정 테이블의 여러 조건(column=value) 기반으로 데이터를 조회한다. 반드시 TABLE_SCHEMA에 정의된 테이블과 컬럼만 사용 가능하다. 값은 숫자 혹은 한국어만 올 수 있다.",
        "input_format": {
            "table_name": "조회할 테이블 이름 (예: 'exercise_record')",
            "conditions": {
                "column1": "값1",
                "column2": "값2"
            }
        }
    },
    {
        "name": "search_exercise_by_name",
        "description": "운동 이름을 검색하여 exercise_id를 조회한다. 검색어는 한국어만 올 수 있다.",
        "input_format": {
            "name": "검색할 운동 이름 (예: '벤치 프레스')"
        }
    }
]

tools = []

def planning(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """사용자 질문과 테이블 정보를 통해 답변 생성 절차를 계획하는 노드"""
    message = state.message
    member_id = 3

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_PLANNING_PROMPT_4),
        ("user", "{message}"),
        ("user", "{member_id}"),
        ("user", "{table_schema}"),
        ("user", "{tool_descriptions}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        verbose=True,
        tools=tools,
        handle_parse_errors=True,
    )

    response = agent_executor.invoke({
        "message": message,
        "member_id": member_id,
        "table_schema": json.dumps(TABLE_SCHEMA, indent=2, ensure_ascii=False),
        "tool_descriptions": json.dumps(TOOL_DESCRIPTIONS, indent=2, ensure_ascii=False),
    })

    print("exercise planning response: ", response["output"])
    state.plan = response["output"]
    return state