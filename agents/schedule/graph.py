from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.graphs import visualize_graph
from chatbot import call_chatbot

# State 정의
class State(TypedDict):
    messages: Annotated[list, add_messages]

def ai_assistant_node(state: State):
    messages = state["messages"]
    ai_response = call_chatbot(messages)
    print(f"\033[1;32m예약 도우미\033[0m: {ai_response}")
    return {"messages": messages + [AIMessage(content=ai_response)]}

def user_node(state: State):
    print("\n")
    user_input = input(f"\033[1;36m사용자\033[0m: ")
    if user_input.strip().upper() == "종료":
        return {"messages": state["messages"] + [HumanMessage(content="종료")]}
    return {"messages": state["messages"] + [HumanMessage(content=user_input)]}

def should_continue(state: State):
    if state["messages"][-1].content == "종료":
        return "end"
    return "continue"

def build_graph():
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
    simulation = build_graph()
    visualize_graph(simulation)

    config = RunnableConfig(recursion_limit=100, configurable={"thread_id": "1"})

    # supervisor로부터 최초로 받는 메시지(input)
    inputs = {
        "messages": [HumanMessage(content="안녕하세요?")]
    }

    # 그래프 스트리밍 실행
    for chunk in simulation.stream(inputs, config):
        pass

if __name__ == "__main__":
    run_graph_simulation() 