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
graph.add_node("ask_user_node", ask_user_node)
graph.add_node("tool_executor", tool_executor_node)
graph.add_node("retry", retry_node)
graph.add_node("refine", refine_node)

# ✅ 진입점
graph.set_entry_point("planner")

# ✅ planner → 다음 노드 조건 분기
graph.add_conditional_edges(
    "planner",
    lambda state: (
        "ask_user_node"
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
        else "refine"
    )
)

# ✅ tool_executor → 다음 노드 분기
graph.add_conditional_edges(
    "tool_executor",
    lambda state: (
        "retry"
        if state.parsed_plan.get("tool_name") not in ["record_meal_tool"]
        else "refine"
    )
)

# ✅ retry → next_node 필드 기반 분기
graph.add_conditional_edges(
    "retry",
    lambda state: state.next_node if state.next_node else "refine"
)

# ✅ 종료 지점 설정
graph.set_finish_point("ask_user_node")
graph.set_finish_point("refine")

# ✅ 컴파일
compiled_graph = graph.compile()
# ✅ 실행 함수
async def run_super_agent(user_input: str, member_id: int, user_info: Optional[Dict[str, Any]] = None):
    # user_info가 None이면 빈 딕셔너리로 초기화
    user_info = user_info or {}
    
    # context에 user_info 추가
    context = {
        "user_info": user_info,
        "user_profile_saved": False  # 기본값 설정
    }
    
    result = await compiled_graph.ainvoke({
        "user_input": user_input,
        "member_id": member_id,
        "context": {},
        "parsed_plan": {},
        "tool_result": "",
        "agent_out": "",
        "retry_count": 0
    })
    
    # 결과가 문자열이 아니면 문자열로 변환
    if isinstance(result, dict) and 'agent_out' in result:
        return str(result['agent_out'])
    elif isinstance(result, dict):
        return str(result)
    else:
        return str(result)


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
