from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from .nodes import pt_schedule_node
from .state import trainerChatState

load_dotenv()
    
def create_pt_schedule_workflow():
    """PT 스케줄 워크플로우 생성"""

    llm = ChatOpenAI(
        model="gpt-4.1-nano",
        temperature=0.56
    )

    workflow = StateGraph(trainerChatState)

    workflow.add_node("pt_schedule", lambda state: pt_schedule_node(state, llm))

    workflow.add_edge(START, "pt_schedule")
    workflow.add_edge("pt_schedule", END)

    result = workflow.compile()
    return result

if __name__ == "__main__":
    workflow = create_pt_schedule_workflow()
    workflow.invoke({"input": "이번달에 취소된 PT 스케줄 있었어?", "trainer_id": 1})
