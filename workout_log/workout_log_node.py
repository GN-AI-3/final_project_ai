from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import Tool
from workout_log.workout_log_prompt import WORKOUT_LOG_PROMPT
from pt_log.pt_log_prompt import PT_LOG_PROMPT_WITH_HISTORY
from workout_log.workout_log_tool import add_workout_log, modify_workout_log, is_workout_log_exist
from workout_log.workout_log_model import workoutLogState
from agents.exercise.tools.exercise_member_tools import search_exercise_by_name
import json

tools = [
    Tool(
        name="add_workout_log",
        func=add_workout_log,
        description=(
            "특정 사용자의 PT 세션에서 수행한 개별 운동 기록을 서버에 저장하는 기능. "
            "다음 정보를 dto 형식으로 구성하여 호출해야 한다:\n"
            "- memberId: 사용자 고유 ID (숫자)\n"
            "- exerciseId: 수행한 운동의 ID (숫자, 사전에 운동명을 검색해서 매핑해야 함)\n"
            "- date: 운동이 수행된 날짜와 시간 (ISO 8601 형식, 예: '2025-04-16T05:44:27.333Z')\n"
            "- recordData: 운동 기록 데이터 (예: {\"sets\": 5, \"reps\": 10, \"weight\": 100})\n"
            "- memoData: 세션 중 느낀 점이나 피드백 (예: {\"memo\": \"어깨가 아프더라니까요\"}) - 세션 중 느낀 점이나 피드백이 없으면 {\"memo\": \"\"} 로 전달\n\n"
        )
    ),
    Tool(
        name="search_exercise_by_name",
        func=search_exercise_by_name,
        description=(
            "운동 이름을 검색하여 exercise_id를 조회한다. 검색어는 한국어만 올 수 있다."
        )
    ),
    Tool(
        name="is_workout_log_exist",
        func=is_workout_log_exist,
        description=(
            "exercise_record 테이블에 해당 운동 기록이 존재하는지 확인한다. 존재하면 exercise_record_id를 반환하고, 존재하지 않으면 None을 반환한다."
            "다음 정보를 dto 형식으로 구성하여 호출해야 한다:\n"
            "- memberId: 사용자 고유 ID (숫자)\n"
            "- exerciseId: 수행한 운동의 ID (숫자, 사전에 운동명을 검색해서 매핑해야 함, **null이 오면 안됨**)\n"
        )
    ),
    Tool(
        name="modify_workout_log",
        func=modify_workout_log,
        description=(
            "exercise_record 에서 기록한 운동 기록을 수정한다. 다음 정보를 dto 형식으로 구성하여 호출해야 한다:\n"
            "- memberId: 사용자 고유 ID (숫자)\n"
            "- exerciseId: 수행한 운동의 ID (숫자, 사전에 운동명을 검색해서 매핑해야 함, **null이 오면 안됨**)\n"
            "- date: 운동이 수행된 날짜와 시간 (ISO 8601 형식, 예: '2025-04-16T05:44:27.333Z', **null이 오면 안됨**)\n"
            "- recordData: 운동 기록 데이터 (예: {\"sets\": 5, \"reps\": 10, \"weight\": 100}) - (선택) sets, reps, weight 모두 있어야 recordData 포함 가능, 하나라도 없으면 포함 불가\n"
            "- memoData: 세션 중 느낀 점이나 피드백 (예: {\"memo\": \"어깨가 아프더라니까요\"}) - (선택) 세션 중 느낀 점이나 피드백이 없으면 memoData 포함 불가\n\n"
        )
    )
]

def workout_log(state: workoutLogState, llm: ChatOpenAI) -> workoutLogState:
    """개인 운동 기록 노드"""

    message = state.message
    memberId = state.memberId
    date = state.date
    chat_history = state.chat_history

    print("chat_history: ", state.chat_history)

    if chat_history and len(chat_history) > 0:
        reconstruct_prompt = ChatPromptTemplate.from_messages([
            ("system", PT_LOG_PROMPT_WITH_HISTORY),
            ("user", "{message}"),
            ("user", "{chat_history}"),
        ])

        reconstruct_chain = reconstruct_prompt | llm
        reconstructed_message = reconstruct_chain.invoke({
            "chat_history": json.dumps(chat_history, ensure_ascii=False),
            "message": message
        }).content
    else:
        reconstructed_message = message

    print("reconstructed_message: ", reconstructed_message)
    prompt = ChatPromptTemplate.from_messages([
        ("system", WORKOUT_LOG_PROMPT),
        ("user", "{reconstructed_message}"),
        ("user", "{memberId}"),
        ("user", "{date}"),
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
        "reconstructed_message": reconstructed_message,
        "memberId": memberId,
        "date": date
    })

    print("workout log response: ", response["output"])
    state.response = response["output"]
    return state