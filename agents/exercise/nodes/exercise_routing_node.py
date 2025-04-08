from typing import Dict, Any
from ..prompts.exercise_routing_prompts import ROUTING_PROMPT
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from ..models.state_models import RoutingState
from langchain.tools import Tool
from ..tools.exercise_routing_tools import save_exercise_record
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import StructuredTool
from ..tools.exercise_routine_tools import get_all_table_schema, master_select_db_multi
from ..models.input_models import MasterSelectMultiInput, EmptyArgs

load_dotenv()

tools = [
    Tool.from_function(
        func=save_exercise_record,
        name="save_exercise_record",
        description="운동 일지 저장"
    ),
    StructuredTool.from_function(
        func=get_all_table_schema,
        name="get_all_table_schema",
        description="사용 가능한 테이블과 컬럼 정보를 조회합니다. 이 툴은 인자를 받지 않습니다.",
        args_schema=EmptyArgs
    ),
    StructuredTool.from_function(
        func=master_select_db_multi,
        name="master_select_db_multi",
        description="PostgreSQL의 모든 테이블에서 여러 조건으로 데이터를 조회합니다. table_name, conditions 모두 필수입니다. table_name은 TABLE_SCHEMA에 정의된 테이블명만 사용할 수 있습니다. conditions 의 키는 TABLE_SCHEMA에 정의된 컬럼명만 사용할 수 있습니다.",
        args_schema=MasterSelectMultiInput
    ),
]

def routing(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """라우팅 노드"""
    message = state.message
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTING_PROMPT),
        ("user", "{message}"),
        ("user", "{user_id}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parse_errors=True,
    )

    user_id = state.user_id

    response = agent_executor.invoke({
        "message": message,
        "user_id": user_id
    })

    print("routing response: ", response["output"])
    state.category = response["output"]
    return state