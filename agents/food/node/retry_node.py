import json
from langchain.schema import HumanMessage
from agents.food.llm_config import llm
from agents.food.tool.recommend_diet_tool import tool_list
from agents.food.agent_state import AgentState

tool_map = {tool.name: tool for tool in tool_list}

def retry_node(state: AgentState) -> AgentState:
    parsed_plan = state.parsed_plan or {}
    tool_result = state.tool_result or ""
    tool_name = parsed_plan.get("tool_name", "")
    user_input = state.user_input
    member_id = state.member_id
    context = state.context or {}
    retry_count = state.retry_count or 0
    max_retry = 2

    # ✅ 평가 대상 도구 목록
    evaluatable_tools = {"recommend_diet_tool", "record_meal_tool"}

    # 1️⃣ 사용자 정보 저장 도구인 경우
    if tool_name == "save_user_goal_and_diet_info" and "추출된 정보" in tool_result:
        prompt = f"""
        아래는 사용자의 입력과 저장된 정보야.
        이 정도 정보면 식단 추천이 가능한가?

        [사용자 입력]
        {user_input}

        [저장 결과]
        {tool_result}

        추가 정보가 더 필요하면 "planner"로 보내고,
        충분하다면 "final"로 종료해줘.

        형식: planner / final
        """
        response = llm.invoke([HumanMessage(content=prompt)]).content.strip().lower()
        if response == "planner":
            return state.copy(update={
                "retry_count": retry_count + 1,
                "agent_out": "ℹ️ 저장된 정보는 충분하지 않아 추가 질문 필요",
                "context": {**context, "user_profile_saved": True}
            })
        return state.copy(update={
            "agent_out": "✅ 사용자 정보 저장 완료 및 충분함",
            "context": {**context, "user_profile_saved": True}
        })
    if state.tool_name == "record_meal_tool":
        return state.copy(update={
            "agent_out": "✅ 식사 기록 도구는 평가 없이 완료됩니다.",
            "next_node": "refine"
        })
    # ✅ 평가 대상이 아닌 도구일 경우 → 평가 생략
    if tool_name not in evaluatable_tools:
        return state.copy(update={
            "agent_out": f"ℹ️ 평가 생략: {tool_name} 도구는 평가 대상이 아닙니다.",
            "context": context
        })

    # 2️⃣ 피드백 도구 확인
    feedback_tool = tool_map.get("diet_feedback_tool")
    if not feedback_tool:
        return state.copy(update={
            "agent_out": "⚠️ 평가 도구(diet_feedback_tool)가 없어 결과를 그대로 반환합니다.",
            "context": context
        })

    # 3️⃣ 도구 피드백 평가
    try:
        feedback = feedback_tool.invoke({"params": {
            "input": tool_result,
            "member_id": member_id,
            "context": context
        }})
        parsed_feedback = json.loads(feedback)
        context["diet_feedback"] = feedback

        # 3-1️⃣ 결과 부적절 → 재시도 or 플래너 or fallback
        if not parsed_feedback.get("valid", True):
            suggestion = parsed_feedback.get("suggestion", "")
            retry_tool = tool_map.get(tool_name)
            retry_input = parsed_plan.get("tool_input", {})

            # 1차: 도구 재실행
            if retry_count == 0 and retry_tool:
                if isinstance(retry_input, dict):
                    retry_input["input"] = retry_input.get("input", "") + f" ({suggestion})"
                retry_result = retry_tool.invoke({"params": {
                    "input": retry_input,
                    "member_id": member_id,
                    "context": context
                }})
                return state.copy(update={
                    "retry_count": retry_count + 1,
                    "context": context,
                    "tool_result": retry_result,
                    "agent_out": f"🔁 재추천 실행됨 (1차)\n→ {retry_result}"
                })

            # 2차: planner 재실행
            if retry_count == 1:
                return state.copy(update={
                    "retry_count": retry_count + 1,
                    "agent_out": "🧠 재시도 실패 → 전체 플래너 재실행",
                    "next_node": "planner",
                    "context": context
                })

            # 3차: LLM Fallback 응답
            fallback_prompt = f"""
            도구 결과가 충분하지 않아서 {max_retry}회 이상 재시도했지만 실패했어.

            [사용자 입력]
            {user_input}

            [현재 context 정보]
            {json.dumps(context, ensure_ascii=False)}

            [도구 실행 결과]
            {tool_result}

            이 상황을 고려해서 LLM이 직접 사용자에게 적절한 응답을 생성해줘.
            """
            response = llm.invoke([HumanMessage(content=fallback_prompt)])
            return state.copy(update={
                "agent_out": f"🤖 도구 실패 → LLM이 직접 응답 생성\n→ {response.content.strip()}",
                "context": context
            })

        # 3-2️⃣ 결과 적절
        return state.copy(update={
            "agent_out": f"✅ 결과 평가 완료: 적절한 결과입니다.\n→ {tool_result}",
            "context": context
        })

    except Exception as e:
        return state.copy(update={
            "agent_out": f"❌ 평가 또는 재시도 실패\n{str(e)}",
            "retry_count": retry_count + 1,
            "context": context
        })
