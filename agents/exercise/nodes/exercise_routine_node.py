from ..models.state_models import RoutingState
from ..prompts.exercise_routine_prompts import EXERCISE_ROUTINE_PROMPT
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.tools import Tool
from ..tools.exercise_routine_tools import web_search, get_user_goal
from ..models.input_models import GetUserInfoInput
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from ..tools.exercise_routine_tools import get_user_physical_info

load_dotenv()

tools = [
    Tool.from_function(
        func=web_search,
        name="web_search",
        description="웹 검색을 통해 운동 루틴 정보를 찾습니다."
    ),
    Tool.from_function(
        func=get_user_goal,
        name="get_user_goal",
        description="PostgreSQL member 테이블에서 특정 사용자 목표 정보를 조회합니다.",
        args_schema=GetUserInfoInput
    ),
    Tool.from_function(
        func=get_user_physical_info,
        name="get_user_physical_info",
        description="PostgreSQL inbody 테이블에서 특정 사용자 신체 정보를 조회합니다.",
        args_schema=GetUserInfoInput
    ),
]

def exercise_routine_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 루틴 추천 노드"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_ROUTINE_PROMPT),
        ("user", "{message}\n\n[USER_ID: {user_id}]"),
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
        "message": state.message,
        "user_id": user_id
    })
    print("exercise form response: ", response["output"])
    state.message = response["output"]
    return state

