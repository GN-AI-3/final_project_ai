from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from ..models.state_models import RoutingState

from ..prompts.exercise_judge_prompts import EXERCISE_JUDGE_PROMPT_ENGLISH

tools = []

def judge(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    """사용자의 메시지에 대한 답변이 적합한지 판단하는 노드"""
    message = state.message
    result = state.result
    context = state.context

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXERCISE_JUDGE_PROMPT_ENGLISH),
        ("user", "{message}"),
        ("user", "{result}"),
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
        "result": result,
    })

    print("exercise judge response: ", response["output"])
    state.context = []
    state.feedback = response["output"]
    return state