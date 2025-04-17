from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import Tool
from pt_log.pt_log_prompt import PT_LOG_PROMPT
from pt_log.pt_log_tool import submit_workout_log, is_workout_log_exist, add_workout_log, is_exercise_log_exist, modify_workout_log
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
    ),
    Tool(
        name="is_workout_log_exist",
        func=is_workout_log_exist,
        description=(
            "ptScheduleId 에 해당하는 PT 운동 세션에 대한 피드백과 기록이 존재하는지 확인한다. 존재하면 pt_log_id를 반환하고, 존재하지 않으면 None을 반환한다."
        )
    ),
    Tool(
        name="add_workout_log",
        func=add_workout_log,
        description=(
            "PT 세션 중 사용자가 수행한 개별 운동을 서버에 추가 저장하는 기능이다. "
            "사용자의 메시지를 기반으로 다음 JSON 형식으로 정보를 추출해서 호출해야 한다:\n\n"
            "{\n"
            '    "ptLogId": 101,              // 필수, 현재 PT 로그 ID (숫자)\n'
            '    "exerciseId": 123,           // 필수, 운동 ID (운동 이름을 검색하여 숫자 ID로 변환해야 함)\n'
            '    "sequence": 1,               // 필수, 운동 순서 (1 이상 정수)\n'
            '    "sets": 3,                   // 필수, 세트 수 (1 이상 정수)\n'
            '    "reps": 10,                  // 필수, 반복 횟수 (1 이상 정수)\n'
            '    "weight": 20,                // 필수, 무게 (0 이상 숫자, kg 단위)\n'
            '    "restTime": 60,              // 선택, 세트 간 휴식 시간 (초 단위)\n'
            '    "feedback": "좋은 자세로 수행"  // 선택, 해당 운동에 대한 피드백\n'
            "}\n\n"
            "- 'ptLogId'는 현재 PT 세션의 로그 ID이며, 반드시 포함되어야 한다.\n"
            "- 'exerciseId'는 반드시 운동 이름을 검색하여 ID(숫자)로 변환해야 하며, 나머지 값들도 자연어에서 정확히 추출해야 한다."
        )
    ),
    Tool(
        name="is_exercise_log_exist",
        func=is_exercise_log_exist,
        description=(
            "ptLogId와 exerciseId에 해당하는 운동 기록이 존재하는지 확인한다. 존재하면 exerciseLogId를 반환하고, 존재하지 않으면 None을 반환한다.\n"
            "ptLogId와 exerciseId는 반드시 포함되어야 한다. ptLogId는 현재 PT 세션의 로그 ID이며, exerciseId는 운동 이름을 검색하여 숫자 ID로 변환해야 한다."
        )
    ),
    Tool(
        name="modify_workout_log",
        func=modify_workout_log,
        description=(
            "이미 존재하는 PT 로그에서 운동 기록을 수정하는 기능이다. "
            "사용자의 메시지를 기반으로 다음 JSON 형식으로 정보를 추출해서 하나의 json 형식으로 호출해야 한다:\n\n"
            "{\n"
            '    "ptLogId": 101,              // 필수, 현재 PT 로그 ID (숫자)\n'
            '    "exerciseLogId": 10,         // 필수, 수정하려는 운동 로그 ID (숫자)\n'
            '    "sequence": 1,               // 선택, 운동 순서 (1 이상 정수)\n'
            '    "sets": 3,                   // 선택, 세트 수 (1 이상 정수)\n'
            '    "reps": 10,                  // 선택, 반복 횟수 (1 이상 정수)\n'
            '    "weight": 20,                // 선택, 무게 (0 이상 숫자, kg 단위)\n'
            '    "restTime": 60,              // 선택, 세트 간 휴식 시간 (초 단위)\n'
            '    "feedback": "좋은 자세로 수행"  // 선택, 해당 운동에 대한 피드백\n'
            "}\n\n"
            "- 'ptLogId'는 현재 PT 세션의 로그 ID이며, 반드시 포함되어야 한다.\n"
            "- 'exerciseLogId'는 수정하려는 운동 기록의 ID로 반드시 포함되어야 한다.\n"
            "- 'sequence', 'sets', 'reps', 'weight'는 선택사항으로, 제공되지 않으면 기존 값으로 남는다.\n"
            "- 'restTime'과 'feedback'은 선택사항으로, 제공되지 않으면 기존 값으로 남는다.\n"
            "- 'sets', 'reps', 'weight' 등의 값은 숫자 형식이어야 한다.\n"
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
    state.response = response["output"]
    return state