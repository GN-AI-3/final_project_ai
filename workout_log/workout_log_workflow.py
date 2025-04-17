from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from workout_log.workout_log_node import workout_log
from workout_log.workout_log_model import workoutLogState

load_dotenv()

def create_workout_log_workflow():
    """개인 운동 기록 워크플로우 생성"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    workflow = StateGraph(workoutLogState)

    workflow.add_node("workout_log", lambda state: workout_log(state, llm))

    workflow.add_edge(START, "workout_log")

    workflow.add_edge("workout_log", END)

    result = workflow.compile()
    print("result: ", result)
    return result

if __name__ == "__main__":
    workflow = create_workout_log_workflow()
    workflow.invoke({"message": "레그프레스하는데 무릎이 아프더라", "memberId": 16, "date": "2025-04-16T05:44:27.333Z"})

