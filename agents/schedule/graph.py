from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from .core.state import State, should_continue
from .core.nodes import create_ai_assistant_node, user_node
from .chatbot import call_chatbot


def build_graph():
    """대화 그래프를 구성합니다.
    
    Returns:
        컴파일된 그래프 객체
    """
    graph_builder = StateGraph(State)

    # 노드 추가 (의존성 주입)
    ai_node = create_ai_assistant_node(call_chatbot)
    graph_builder.add_node("사용자", user_node)
    graph_builder.add_node("예약 도우미", ai_node)

    # 엣지 정의
    graph_builder.add_edge("예약 도우미", "사용자")

    # 조건부 엣지 정의
    graph_builder.add_conditional_edges(
        "사용자",
        should_continue,
        {
            "end": END,
            "continue": "예약 도우미",
        },
    )

    graph_builder.set_entry_point("예약 도우미")
    return graph_builder.compile() 