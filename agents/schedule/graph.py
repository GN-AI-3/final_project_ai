from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.graphs import visualize_graph

from core.state import State, should_continue
from core.nodes import ai_assistant_node, user_node


def build_graph():
    """대화 그래프를 구성합니다.
    
    Returns:
        컴파일된 그래프 객체
    """
    graph_builder = StateGraph(State)

    # 노드 추가
    graph_builder.add_node("사용자", user_node)
    graph_builder.add_node("예약 도우미", ai_assistant_node)

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


def run_graph_simulation():
    """그래프 시뮬레이션을 실행합니다."""
    simulation = build_graph()
    visualize_graph(simulation)

    config = RunnableConfig(
        recursion_limit=2147483647, 
        configurable={"thread_id": "7"}
    )

    # supervisor로부터 최초로 받는 메시지(input)
    inputs = {
        "messages": [HumanMessage(content="안녕하세요?")]
    }

    # 그래프 스트리밍 실행
    for chunk in simulation.stream(inputs, config):
        pass


if __name__ == "__main__":
    run_graph_simulation() 