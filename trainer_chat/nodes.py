from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from .pt_schedule_state import ptScheduleState
from .prompts import PT_SCHEDULE_PROMPT
from .tools import gen_pt_schedule_query
from .sql_tools import excute_query

def pt_schedule_node(state: ptScheduleState, model: ChatOpenAI) -> ptScheduleState:
    """PT 스케줄 관리 노드"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PT_SCHEDULE_PROMPT),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    tools=[gen_pt_schedule_query, excute_query]
    
    agent = create_tool_calling_agent(model, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    response = agent_executor.invoke({
        "input": state.input,
        "trainer_id": state.trainer_id,
        "chat_history": state.chat_history,
    })

    state.response = response["output"]
    return state