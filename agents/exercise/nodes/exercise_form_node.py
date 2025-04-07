from ..models.state_models import RoutingState
from ..prompts.exercise_form_prompts import EXERCISE_FORM_PROMPT, CONFIRM_EXERCISE_FORM_PROMPT
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from ..tools.exercise_form_tools import web_search, get_user_info, get_exercise_info
from dotenv import load_dotenv
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from ..models.input_models import GetUserInfoInput

load_dotenv()

tools = [
    Tool.from_function(
        func=web_search,
        name="web_search",
        description="웹 검색을 통해 운동 자세 정보를 찾습니다."
    ),
    Tool.from_function(
        func=get_user_info,
        name="get_user_info",
        description="PostgreSQL member 테이블에서 특정 사용자 정보를 조회합니다.",
        args_schema=GetUserInfoInput
    ),
    Tool.from_function(
        func=get_exercise_info,
        name="get_exercise_info",
        description="운동 명칭에 대한 기본 정보를 제공합니다."
    ),
]

def exercise_form_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 자세 추천 노드"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_FORM_PROMPT),
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

def confirm_exercise_form_agent(state: RoutingState, llm: ChatOpenAI):
    """추천된 운동 자세 관련 메시지를 확인하고 수정 요청 노드"""
    # tools = [web_search]
    # agent = llm.bind_tools(tools)
    message = state.message
    prompt = CONFIRM_EXERCISE_FORM_PROMPT.format(message=message)
    response = llm.invoke(prompt)
    print("confirm exercise form response: ", response.content)
    state.message = response.content
    return state
