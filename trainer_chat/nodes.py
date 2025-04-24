from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from .pt_schedule_state import ptScheduleState
from .prompts import PT_SCHEDULE_PROMPT
from .tools import get_pt_schedule
from .sql_tools import relative_time_expr_to_sql

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
    tools=[get_pt_schedule, relative_time_expr_to_sql]
    
    agent = create_tool_calling_agent(model, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    from langchain_core.messages import AIMessage, HumanMessage

    response = agent_executor.invoke({
        "input": state.input,
        "trainer_id": state.trainer_id,
        "chat_history": state.chat_history,
        "sql_time_expr": state.sql_time_expr,
    })

    state.response = response["output"]
    return state