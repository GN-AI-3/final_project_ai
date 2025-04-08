from ..models.state_models import RoutingState
from ..prompts.exercise_routine_prompts import EXERCISE_ROUTINE_PROMPT_2
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.tools import Tool, StructuredTool
from ..tools.exercise_routine_tools import web_search, get_user_goal, get_user_physical_info, get_user_exercise_record, master_select_db, get_all_table_schema
from ..models.input_models import GetUserInfoInput, MasterSelectInput
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate

load_dotenv()

tools = [
    # Tool.from_function(
    #     func=web_search,
    #     name="web_search",
    #     description="웹 검색을 통해 운동 루틴 정보를 찾습니다."
    # ),
    # Tool.from_function(
    #     func=get_user_goal,
    #     name="get_user_goal",
    #     description="PostgreSQL member 테이블에서 특정 사용자 목표 정보를 조회합니다.",
    #     args_schema=GetUserInfoInput
    # ),
    # Tool.from_function(
    #     func=get_user_physical_info,
    #     name="get_user_physical_info",
    #     description="PostgreSQL inbody 테이블에서 특정 사용자 신체 정보를 조회합니다.",
    #     args_schema=GetUserInfoInput
    # ),
    # Tool.from_function(
    #     func=get_user_exercise_record,
    #     name="get_user_exercise_record",
    #     description="PostgreSQL exercise_record 테이블에서 특정 사용자 운동 기록을 조회합니다.",
    #     args_schema=GetUserInfoInput
    # ),
    Tool.from_function(
        func=web_search,
        name="web_search",
        description="웹 검색을 통해 운동 루틴 정보를 찾습니다."
    ),
    Tool.from_function(
        func=get_all_table_schema,
        name="get_all_table_schema",
        description="사용 가능한 테이블과 컬럼 정보를 조회합니다.",
        return_direct=True
    ),
    StructuredTool.from_function(
        func=master_select_db,
        name="master_select_db",
        description="PostgreSQL의 모든 테이블에서 데이터를 조회합니다. table_name, column_name, value 모두 필수입니다.",
        args_schema=MasterSelectInput
    )
]

def exercise_routine_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 루틴 추천 노드"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_ROUTINE_PROMPT_2),
        ("user", "{message}\n\n[MEMBER_ID: {member_id}]"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        handle_parse_errors=True,
    )

    member_id = state.user_id

    response = agent_executor.invoke({
        "message": state.message,
        "member_id": member_id
    })
    print("exercise form response: ", response["output"])
    state.message = response["output"]
    return state

