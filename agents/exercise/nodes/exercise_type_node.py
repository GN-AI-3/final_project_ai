from ..models.state_models import RoutingState
from ..prompts.exercise_routing_prompts import EXERCISE_TYPE_PROMPT
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def exercise_type_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 종류 추천 노드"""
    message = state.message
    prompt = EXERCISE_TYPE_PROMPT.format(message=message)
    response = llm.invoke(prompt)
    print("exercise type response: ", response.content)
    state.message = response.content
    return state

