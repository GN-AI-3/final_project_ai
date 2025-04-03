from ..models.state_models import RoutingState
from ..prompts.exercise_form_prompts import EXERCISE_FORM_PROMPT, CONFIRM_EXERCISE_FORM_PROMPT
from langchain_openai import ChatOpenAI
from ..tools.exercise_form_tools import web_search, get_user_info, get_exercise_info
from dotenv import load_dotenv

load_dotenv()

def exercise_form_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 자세 추천 노드"""
    tools = [web_search]
    agent = llm.bind_tools(tools)
    message = state.message
    prompt = EXERCISE_FORM_PROMPT.format(message=message)
    response = agent.invoke(prompt)

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name == "web_search":
                search_result = web_search.invoke(tool_args["query"])
                state.message += f"웹 검색 결과: {search_result}"

        prompt = EXERCISE_FORM_PROMPT.format(message=state.message)
        response = agent.invoke(prompt)

    print("exercise form response: ", response.content)
    state.message = response.content
    return state

def confirm_exercise_form_agent(state: RoutingState, llm: ChatOpenAI):
    """추천된 운동 자세 관련 텍스트를 확인하고 수정 요청 노드"""
    tools = [web_search]
    agent = llm.bind_tools(tools)
    message = state.message
    prompt = CONFIRM_EXERCISE_FORM_PROMPT.format(message=message)
    response = agent.invoke(prompt)
    print("confirm exercise form response: ", response.content)
    state.message = response.content
    return state
