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
