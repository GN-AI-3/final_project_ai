from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from ..models.state_models import RoutingState
from ..prompts.exercise_planning_prompts import EXERCISE_PLANNING_PROMPT_4
import json

TABLE_SCHEMA_FOR_MEMBER = {
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "foreign_keys": {
            "member_id": "member.id",
            "exercise_id": "exercise.id"
        },
        "description": "사용자의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "goal"],
        "description": "사용자 정보. goal은 사용자의 운동 목표입니다 (예: 벌크업, 체중 감량)."
    }
}

TOOL_DESCRIPTIONS_FOR_MEMBER = [
    {
        "name": "web_search",
        "description": "웹 검색을 통해 필요한 정보를 수집한다. query에는 검색어 문자열을 넣는다.",
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
            "name": "검색할 운동 이름"
        }
    },
    {
        "name": "retrieve_exercise_info_by_similarity",
        "description": "사용자의 질문이나 운동 관련 문장을 기반으로, 유사한 운동 정보를 벡터 DB(Qdrant)에서 조회한다. 이 툴은 운동명뿐 아니라 전체 운동 설명, 목적, 자세 등을 검색하는 데 사용된다.",
        "input_format": {
            "query": "운동 정보 검색을 위한 문장 또는 키워드를 영어로 입력한다. (e.g., 'exercises to build a wider back', 'leg workouts that are easy on the knees')"
        }
    }
]

TABLE_SCHEMA_FOR_TRAINER = {
    "exercise_record": {
        "columns": ["id", "member_id", "exercise_id", "date", "record_data", "memo_data"],
        "foreign_keys": {
            "member_id": "member.id",
            "exercise_id": "exercise.id"
        },
        "description": "회원의 개별 운동 수행 기록. record_data는 세트/반복/무게 등의 상세 기록이며, memo_data는 자유 메모입니다."
    },
    "member": {
        "columns": ["id", "name", "email", "phone", "goal"],
        "description": "회원 정보. goal은 회원의 운동 목표입니다 (예: 벌크업, 체중 감량). 회원을 조회해야하는 경우엔 동명이인이 있을 수 있으므로 반드시 pt_contract 테이블을 조회해야 한다. "
    },
    "pt_contract" : {
        "columns": ["id","member_id", "trainer_id"],
        "foreign_keys": {
            "member_id": "member.id",
            "trainer_id": "trainer.id"
        },
        "description": "PT 계약 정보, 이 테이블에서 트레이너의 회원 정보를 조회할 수 있다."
    },
    "pt_log": {
        "columns": ["id", "member_id", "trainer_id"],
        "foreign_keys": {
            "member_id": "member.id",
            "trainer_id": "trainer.id"
        },
        "description": "PT 수업 일지"
    },
    "pt_log_exercise": {
        "columns": ["id", "pt_log_id", "exercise_id", "sets", "reps", "weight"],
        "foreign_keys": {
            "pt_log_id": "pt_log.id",
            "exercise_id": "exercise.id"
        },
        "description": "PT 수업 일지에 포함된 운동 정보"
    }
}

TOOL_DESCRIPTIONS_FOR_TRAINER = [
    {
        "name": "web_search",
        "description": "웹 검색을 통해 필요한 정보를 수집한다. query에는 검색어 문자열을 넣는다.",
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
            "name": "검색할 운동 이름"
        }
    },
    {
        "name": "retrieve_exercise_info_by_similarity",
        "description": "사용자의 질문이나 운동 관련 문장을 기반으로, 유사한 운동 정보를 벡터 DB(Qdrant)에서 조회한다. 이 툴은 운동명뿐 아니라 전체 운동 설명, 목적, 자세 등을 검색하는 데 사용된다.",
        "input_format": {
            "query": "운동 정보 검색을 위한 문장 또는 키워드를 영어로 입력한다. (e.g., 'exercises to build a wider back', 'leg workouts that are easy on the knees')"
        }
    }
]

tools = []

def planning(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """사용자 질문과 테이블 정보를 통해 답변 생성 절차를 계획하는 노드"""

    message = state.message
    feedback = state.feedback
    member_id = state.member_id
    trainer_id = state.trainer_id

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_PLANNING_PROMPT_4),
        ("user", "{message}"),
        ("user", "{member_id}"),
        ("user", "{table_schema}"),
        ("user", "{tool_descriptions}"),
        ("user", "{feedback}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        verbose=True,
        tools=tools,
        handle_parse_errors=True,
    )

    print("User type: ", state.user_type)
    if state.user_type == "member":
        response = agent_executor.invoke({
            "message": message,
            "member_id": member_id,
            "trainer_id": None,
            "table_schema": json.dumps(TABLE_SCHEMA_FOR_MEMBER, indent=2, ensure_ascii=False),
            "tool_descriptions": json.dumps(TOOL_DESCRIPTIONS_FOR_MEMBER, indent=2, ensure_ascii=False),
            "feedback": feedback
        })
    elif state.user_type == "trainer":
        response = agent_executor.invoke({
            "message": message,
            "member_id": None,
            "trainer_id": trainer_id,
            "table_schema": json.dumps(TABLE_SCHEMA_FOR_TRAINER, indent=2, ensure_ascii=False),
            "tool_descriptions": json.dumps(TOOL_DESCRIPTIONS_FOR_TRAINER, indent=2, ensure_ascii=False),
            "feedback": feedback
        })
    else:
        # 기본적으로 trainer 설정을 사용 (미확인 user_type일 경우)
        print(f"Warning: Unknown user_type '{state.user_type}', using trainer settings as default")
        response = agent_executor.invoke({
            "message": message,
            "member_id": None,
            "trainer_id": trainer_id,
            "table_schema": json.dumps(TABLE_SCHEMA_FOR_TRAINER, indent=2, ensure_ascii=False),
            "tool_descriptions": json.dumps(TOOL_DESCRIPTIONS_FOR_TRAINER, indent=2, ensure_ascii=False),
            "feedback": feedback
        })

    print("exercise planning response: ", response["output"])
    state.plan = response["output"]
    return state