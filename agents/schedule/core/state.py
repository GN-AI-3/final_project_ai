from typing import Annotated

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    """대화 상태를 나타내는 클래스
    
    Attributes:
        messages: 대화 메시지 리스트
    """
    messages: Annotated[list, add_messages]


def should_continue(state: State) -> str:
    """대화를 계속할지 결정합니다.
    
    Args:
        state: 현재 대화 상태
        
    Returns:
        str: 'end' 또는 'continue'
    """
    if state["messages"][-1].content == "종료":
        return "end"
    return "continue" 