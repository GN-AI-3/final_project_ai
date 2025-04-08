from ..tools.exercise_routine_tools import get_all_table_schema
from langchain.tools import StructuredTool
from ..models.input_models import EmptyArgs
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from ..models.state_models import RoutingState
from ..prompts.exercise_planning_prompts import EXERCISE_PLANNING_PROMPT

TABLE_SCHEMA = {
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "description": "사용자의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다. exercise_id는 exercise 테이블의 id와 연결해 운동 이름(name)을 조회해야 합니다."
    },
    "exercise": {
        "columns": ["id", "name", "exercise_type"],
        "description": "운동 목록. name은 운동명이며, exercise_type은 카테고리입니다 (예: 유산소 등)."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "profile_image", "goal"],
        "description": "사용자 정보. goal은 사용자의 운동 목표입니다 (예: 벌크업, 체중 감량)."
    }
}

tools = []

def planning(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """사용자 질문과 테이블 정보를 통해 답변 생성 절차를 계획하는 노드"""
    message = state.message
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_PLANNING_PROMPT),
        ("user", "{message}"),
        ("user", "{member_id}"),
        ("user", "{table_schema}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        verbose=True,
        tools=tools,
        handle_parse_errors=True,
    )

    member_id = state.user_id

    response = agent_executor.invoke({
        "message": message,
        "member_id": member_id,
        "table_schema": TABLE_SCHEMA
    })

    print("exercise planning response: ", response["output"])
    state.category = response["output"]
    return state