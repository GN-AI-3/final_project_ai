from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import Tool
from pt_log.pt_log_prompt import PT_LOG_PROMPT
from pt_log.pt_log_tool import submit_workout_log
from pt_log.pt_log_model import ptLogState
from agents.exercise.tools.exercise_member_tools import search_exercise_by_name
import json

tools = [
    Tool(
        name="submit_workout_log",
        func=submit_workout_log,
        description=(
            "PT 운동 세션에 대한 피드백과 기록을 서버에 저장하는 기능. "
            "사용자의 메시지를 기반으로 다음 정보를 추출해서 호출해야 한다:\n"
            "- ptScheduleId (필수, 현재 세션 ID)\n"
            "- feedback (세션 전체에 대한 소감)\n"
            "- injuryCheck (부상 유무: True/False)\n"
            "- nextPlan (다음 세션 요청사항)\n"
            "- exercises (각 운동의 세트 수, 반복 횟수, 무게, 휴식 시간, 피드백 포함한 리스트) - 반드시 운동 이름을 검색하여 exercise_id를 조회해야 한다. exercise_id는 무조건 숫자로 올 수 있다."
        )
    ),
    Tool(
        name="search_exercise_by_name",
        func=search_exercise_by_name,
        description=(
            "운동 이름을 검색하여 exercise_id를 조회한다. 검색어는 한국어만 올 수 있다."
        )
    )
]

def pt_log_save(state: ptLogState, llm: ChatOpenAI) -> ptLogState:
    """PT 일지 기록 노드"""

    message = state.message
    ptScheduleId = state.ptScheduleId

    prompt = ChatPromptTemplate.from_messages([
        ("system", PT_LOG_PROMPT),
        ("user", "{message}"),
        ("user", "{ptScheduleId}"),
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
        "ptScheduleId": ptScheduleId,
    })

    print("pt log response: ", response["output"])
    state.plan = response["output"]
    return state