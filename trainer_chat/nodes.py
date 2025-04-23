from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.tools import Tool

from .pt_schedule_state import ptScheduleState
from .prompts import RECONSTRUCTED_MESSAGE_PROMPT, PT_SCHEDULE_PROMPT
from .tools import get_pt_schedule
import json

tools=[
    Tool(
        name="get_pt_schedule",
        func=get_pt_schedule,
        description=(
            "PT 스케줄 DB 조회"
        )
    )
]

def pt_schedule_node(state: ptScheduleState, llm: ChatOpenAI) -> ptScheduleState:
    """PT 스케줄 관리 노드"""

    message = state.message
    trainer_id = state.trainer_id
    chat_history = state.chat_history

    # 1. 채팅 내역이 있는 경우 메시지 재구성
    if chat_history and len(chat_history) > 0:
        reconstruct_prompt = ChatPromptTemplate.from_messages([
            ("system", RECONSTRUCTED_MESSAGE_PROMPT),
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

    # 2. 재구성된 메시지로 PT 로그 저장
    prompt = ChatPromptTemplate.from_messages([
        ("system", PT_SCHEDULE_PROMPT),
        ("user", "{reconstructed_message}"),
        ("user", "{trainer_id}"),
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
        "trainer_id": trainer_id,
        "data": {
            "user_input": message,
            "trainer_id": trainer_id
        }
    })

    print("pt log response: ", response["output"])
    state.response = response["output"]
    return state