from langgraph.graph import StateGraph, END, START
from ..nodes.exercise_planning_node import planning
from ..nodes.exercise_judge_node import judge
from ..nodes.exercise_execute_node import execute_plan
from ..nodes.exercise_routing_node import routing
from ..models.state_models import RoutingState
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

    workflow.add_node("exercise_routing", lambda state: routing(state, llm))

    workflow.add_node("exercise_planning", lambda state: planning(state, llm))
    workflow.add_node("exercise_execute", lambda state: execute_plan(state, llm))
    workflow.add_node("exercise_judge", lambda state: judge(state, llm))

    workflow.add_edge(START, "exercise_routing")
    workflow.add_edge("exercise_routing", "exercise_planning")
    workflow.add_edge("exercise_planning", "exercise_execute")
    workflow.add_edge("exercise_execute", "exercise_judge")
    
    workflow.add_conditional_edges(
        "exercise_judge", 
        lambda state: "success" if state.feedback.strip() == "success" else "failure",
        {
            "success": END,
            "failure": "exercise_planning"
        }
    )

    return workflow.compile()