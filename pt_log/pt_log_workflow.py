from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pt_log.pt_log_node import pt_log_save
from pt_log.pt_log_model import ptLogState

load_dotenv()

def create_pt_log_workflow():
    """PT 일지 워크플로우 생성"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    workflow = StateGraph(ptLogState)

    workflow.add_node("pt_log", lambda state: pt_log_save(state, llm))

    workflow.add_edge(START, "pt_log")

    workflow.add_edge("pt_log", END)

    result = workflow.compile()
    print("result: ", result)
    return result

if __name__ == "__main__":
    workflow = create_pt_log_workflow()
    workflow.invoke({"message": "오늘 벤치프레스 10kg 10회 5세트랑 레그프레스 8회 4세트 했어"})

