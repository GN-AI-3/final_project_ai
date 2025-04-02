from ..models.state_models import RoutingState
from ..prompts.system_prompts import EXERCISE_FORM_PROMPT
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def exercise_form_agent(state: RoutingState, llm: ChatOpenAI):
    """운동 자세 추천 노드"""
    message = state.message
    prompt = EXERCISE_FORM_PROMPT.format(message=message)
    response = llm.invoke(prompt)
    print("exercise form response: ", response.content)
    state.message = response.content
    return state

