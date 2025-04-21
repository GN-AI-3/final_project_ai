# 🔧 tool_executor_node.py
import json
from agents.food.tool.recommend_diet_tool import tool_list
from langchain.schema import HumanMessage
from agents.food.llm_config import llm
from agents.food.agent_state import AgentState

tool_map = {tool.name: tool for tool in tool_list}

def tool_executor_node(state: AgentState) -> AgentState:
    parsed_plan = state.parsed_plan or {}
    tool_name = parsed_plan.get("tool_name", "")
    tool_input = parsed_plan.get("tool_input", {})
    member_id = state.member_id
    context = state.context or {}


    tool_fn = tool_map.get(tool_name)

    if not tool_fn:
        return AgentState(
            user_input=state.user_input,
            member_id=state.member_id,
            agent_out=f"❌ 존재하지 않는 도구입니다: {tool_name}",
            context=context,
            tool_result="",
            retry_count=state.retry_count,
            tool_name=tool_name,
            tool_input=tool_input
        )

    try:
        # ✅ 문자열 입력일 경우 감싸기
        if isinstance(tool_input, str):
            tool_input = {"input": tool_input}

        # ✅ 공통 필수 파라미터 추가
        tool_input["member_id"] = member_id
        tool_input["context"] = context

        # ✅ 자연어 입력도 명시적으로 포함 (필요한 도구 대비)
        if "input" not in tool_input:
            tool_input["input"] = state.user_input

        # ✅ 도구 실행 (LangChain Tool은 {"params": ...} 구조 필요)
        result = tool_fn.invoke({"params": tool_input})

        # ✅ 저장 완료 여부 표시
        if tool_name == "save_user_goal_and_diet_info":
            context["user_profile_saved"] = True

        return AgentState(
            user_input=state.user_input,
            member_id=state.member_id,
            parsed_plan=state.parsed_plan,
            context=context,
            tool_result=result,
            agent_out=f"✅ {tool_name} 실행 결과\n→ {result}",
            retry_count=0,
            tool_name=tool_name,
            tool_input=tool_input
        )

    except Exception as e:
        return AgentState(
            user_input=state.user_input,
            member_id=state.member_id,
            parsed_plan=state.parsed_plan,
            context=context,
            tool_result="",
            agent_out=f"❌ 도구 실행 실패: {tool_name}\n에러: {str(e)}",
            retry_count=state.retry_count + 1,
            tool_name=tool_name,
            tool_input=tool_input
        )
