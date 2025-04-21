from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from report.report_exercise_node import analyze_pt_log, add_data, analyze_inbody_data
from report.report_model import reportState

load_dotenv()

def create_report_workflow():
    """PT 일지 워크플로우 생성"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    workflow = StateGraph(reportState)

    workflow.add_node("analyze_exercise_report", lambda state: analyze_pt_log(state, llm))
    workflow.add_node("analyze_inbody_report", lambda state: analyze_inbody_data(state, llm))
    workflow.add_node("add_data", lambda state: add_data(state, llm))

    workflow.add_edge(START, "analyze_exercise_report")
    workflow.add_edge("analyze_exercise_report", "analyze_inbody_report")
    workflow.add_edge("analyze_inbody_report", "add_data")
    workflow.add_edge("add_data", END)

    result = workflow.compile()
    print("result: ", result)
    return result

if __name__ == "__main__":
    workflow = create_report_workflow()
    workflow.invoke({"ptContractId": 1})

