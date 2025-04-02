from typing import Dict, Any
from ..prompts.system_prompts import ROUTING_PROMPT
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from ..models.state_models import RoutingState

load_dotenv()

def routing(state: RoutingState) -> RoutingState:
    """라우팅 노드"""
    message = state["message"]
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    prompt = ROUTING_PROMPT.format(question=message)
    response = llm.invoke(prompt)
    print("response: ", response.content)
    state["category"] = response.content
    return state