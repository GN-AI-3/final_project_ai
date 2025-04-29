# retry_node.py
import json
import re
from langchain.schema import HumanMessage
from agents.food.llm_config import llm
from agents.food.tool.recommend_diet_tool import tool_list
from agents.food.agent_state import AgentState

# tool 이름 → tool 객체 매핑
tool_map = {tool.name: tool for tool in tool_list}

def extract_json_block(text: str) -> str:
    """텍스트에서 JSON 블록 추출 (```json ... ``` 안 or 그냥 { ... } 형태)"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else "{}"

def retry_node(state: AgentState) -> AgentState:
    parsed_plan = state.parsed_plan or {}
    tool_result = state.tool_result or ""
    tool_name = parsed_plan.get("tool_name", "")
    user_input = state.user_input
    member_id = state.member_id
    context = state.context or {}
    retry_count = state.retry_count or 0
    max_retry = 3  # 최대 2회 시도 (retry → planner → smart tool)

    score_threshold = 70  # ✅ 점수 기준: 70점 이상이면 통과

    # 1️⃣ 평가 없이 통과하는 예외 도구 (record_meal_tool)
    if tool_name == "record_meal_tool":
        return state.copy(update={
            "agent_out": "✅ 식사 기록 도구는 평가 없이 완료됩니다.",
            "next_node": "refine"
        })

    # 2️⃣ 평가 프롬프트 작성
    prompt = f"""
너는 AI 평가자야.
아래는 사용자의 입력과 도구 실행 결과야.

[사용자 입력]
{user_input}

[도구 결과]
{tool_result}

이 결과가 사용자 입력에 대한 결과값으로  얼마나 적절한지 0~100점으로 평가해줘.

[판단 기준]
- 90점 이상: 매우 적절
- 70~89점: 적절
- 50~69점: 다소 부적절
- 50점 미만: 부적절

[응답 포맷]
    ```json
    {{
    "score": (0~100 정수),
    "reason": "간단한 이유"
    }}
    반드시 위 JSON 포맷으로만 응답해. """
    try:
        # 3️⃣ LLM을 통한 평가
        evaluation = llm.invoke([HumanMessage(content=prompt)]).content
        parsed_eval = json.loads(extract_json_block(evaluation))
        score = parsed_eval.get("score", 0)
        reason = parsed_eval.get("reason", "")

        # 평가 결과를 context에 저장
        context["last_evaluation"] = {
            "tool_name": tool_name,
            "score": score,
            "reason": reason
        }

        # 4️⃣ 점수로 판단
        if score >= score_threshold:
            # ✅ 점수 통과
            return state.copy(update={
                "agent_out": f"✅ 평가 통과 ({score}점): {reason}",
                "context": context,
                "next_node": "refine"
            })

        # 5️⃣ 점수 미달 → 재시도 흐름
        suggestion_text = f"({reason})" if reason else "(추가 보완 필요)"

        # 1차 재시도 (retry tool)
        if retry_count == 0:
            retry_tool = tool_map.get(tool_name)
            retry_input = parsed_plan.get("tool_input", {}).copy()

            if retry_tool and isinstance(retry_input, dict):
                retry_input["input"] = retry_input.get("input", "") + f" {suggestion_text}"

                retry_result = retry_tool.invoke({"params": {
                    "input": retry_input,
                    "member_id": member_id,
                    "context": context
                }})

                return state.copy(update={
                    "retry_count": retry_count + 1,
                    "tool_result": retry_result,
                    "context": context,
                    "agent_out": f"🔁 1차 재실행 완료 - {suggestion_text}"
                })

        # 2차 재시도 (planner 호출)
        if retry_count == 1:
            return state.copy(update={
                "retry_count": retry_count + 1,
                "agent_out": "🧠 1차 재시도 실패 → 플래너로 돌아갑니다.",
                "next_node": "planner",
                "context": context
            })

        # 3차 재시도 (smart_nutrition_resolver 호출)
        if retry_count >= max_retry:
            smart_tool = tool_map.get("smart_nutrition_resolver")
            if smart_tool:
                smart_result = smart_tool.invoke({"params": {
                    "input": user_input,
                    "member_id": member_id,
                    "context": context
                }})
                return state.copy(update={
                    "agent_out": f"🔍 슈퍼 도구로 재시도 완료\n→ {smart_result}",
                    "context": context
                })

        # 예외 대비 기본 반환
        return state.copy(update={
            "agent_out": f"⚠️ 알 수 없는 상태. {retry_count}회 시도됨",
            "context": context
        })

    except Exception as e:
        return state.copy(update={
            "agent_out": f"❌ 평가 실패 또는 JSON 파싱 오류: {str(e)}",
            "retry_count": retry_count + 1,
            "context": context
        })
