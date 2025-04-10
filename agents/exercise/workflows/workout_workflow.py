from langgraph.graph import StateGraph, END, START
from ..nodes.exercise_routing_node import routing
from ..models.state_models import RoutingState
from ..nodes.exercise_routine_node import exercise_routine_agent
from ..nodes.exercise_form_node import exercise_form_agent, confirm_exercise_form_agent
from ..nodes.exercise_type_node import exercise_type_agent
from ..nodes.exercise_planning_node import planning
from ..nodes.exercise_execute_node import execute_plan
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def create_workout_workflow():
    """운동 워크플로우 생성"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    workflow = StateGraph(RoutingState)

    # 노드 추가
    # workflow.add_node("routing", lambda state: routing(state, llm))
    # workflow.add_node("exercise_routine", lambda state: exercise_routine_agent(state, llm))
    # workflow.add_node("exercise_form", lambda state: exercise_form_agent(state, llm))
    # workflow.add_node("exercise_type", lambda state: exercise_type_agent(state, llm))
    # workflow.add_node("confirm_exercise_form", lambda state: confirm_exercise_form_agent(state, llm))

    workflow.add_node("exercise_planning", lambda state: planning(state, llm))
    workflow.add_node("exercise_execute", lambda state: execute_plan(state, llm))

    # 엣지 추가
    # workflow.add_edge(START, "routing")
    # workflow.add_conditional_edges(
    #     "routing", lambda state: state.category,
    #     {
    #         "운동 루틴": "exercise_routine",
    #         "운동 자세": "exercise_form",
    #         "운동 종류": "exercise_type"
    #     }
    # )

    # workflow.add_edge("exercise_form", END)
    # workflow.add_edge("exercise_type", END)
    # workflow.add_edge("exercise_routine", END)

    workflow.add_edge(START, "exercise_planning")
    workflow.add_edge("exercise_planning", "exercise_execute")
    workflow.add_edge("exercise_execute", END)
    
    return workflow.compile()