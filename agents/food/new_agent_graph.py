# 🧠 new_agent_graph.py
import sys
import os
from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph
from langgraph.channels import LastValue
from agents.food.node.refine_node import refine_node

# 📁 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# ✅ 노드 불러오기
from agents.food.agent_state import AgentState
from agents.food.node.planner_node import planner_node
from agents.food.node.ask_user_node import ask_user_node
from agents.food.node.tool_executor_node import tool_executor_node
from agents.food.node.retry_node import retry_node

# ✅ 그래프 정의
graph = StateGraph(AgentState)

# ✅ 노드 등록
graph.add_node("planner", planner_node)
graph.add_node("ask_user", ask_user_node)
graph.add_node("tool_executor", tool_executor_node)
graph.add_node("retry", retry_node)
graph.add_node("refine", refine_node)
# ✅ 진입점
graph.set_entry_point("planner")
 
graph.add_conditional_edges(
    "planner",
    lambda state: (
        "ask_user"
        if state.parsed_plan.get("ask_user") and len(state.parsed_plan["ask_user"]) > 0
        else "tool_executor"
        if state.parsed_plan.get("tool_name") == "save_user_goal_and_diet_info"
        else "tool_executor"
        if state.parsed_plan.get("need_tool") is True
        else "refine"
        if (
            not state.parsed_plan.get("ask_user") and
            not state.parsed_plan.get("need_tool") and
            state.parsed_plan.get("final_output")
        )
        else "refine"  # 혹시나 예외 상황에도 안전하게
    )
)



graph.add_conditional_edges(
    "tool_executor",
    lambda state: (
        # 저장 완료 안 됐으면 다시 planner 로
        "planner"
        if state.parsed_plan.get("tool_name") == "save_user_goal_and_diet_info"
        and not state.context.get("user_profile_saved")
        else "retry"
    )
)
# ✅ 실행 흐름 연결
graph.add_edge("tool_executor", "retry")
graph.add_edge("retry", "refine")

# ✅ 종료 지점 설정
graph.set_finish_point("ask_user")  # 질문만 있을 때 종료
graph.set_finish_point("refine")  
# ✅ 컴파일
compiled_graph = graph.compile()

# ✅ 실행 함수
def run_super_agent(user_input: str, member_id: int = 3):
    return compiled_graph.invoke({
        "user_input": user_input,
        "member_id": member_id,
        "context": {},
        "parsed_plan": {},
        "tool_result": "",      # ✅ 추가
        "agent_out": "",        # ✅ 추가
        "retry_count": 0        # ✅ 추가
    })


# ✅ 질문 응답 후 재시작 함수
def resume_super_agent(prev_state: dict, user_reply: str):
    prev_state = {
        **prev_state,
        "user_input": user_reply,
        "tool_result": prev_state.get("tool_result", ""),
        "agent_out": prev_state.get("agent_out", ""),
        "retry_count": prev_state.get("retry_count", 0),
    }
    return compiled_graph.resume(prev_state, {})
