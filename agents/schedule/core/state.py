from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage

class State(TypedDict):
    """대화 상태를 나타내는 클래스"""
    messages: Annotated[list, add_messages]

def should_continue(state: State) -> str:
    """대화를 계속할지 결정합니다."""
    if state["messages"][-1].content == "종료":
        return "end"
    return "continue" 