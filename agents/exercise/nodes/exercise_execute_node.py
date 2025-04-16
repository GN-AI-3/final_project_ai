from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
import json
from ..tools.exercise_member_tools import master_select_db_multi, web_search, search_exercise_by_name, retrieve_exercise_info_by_similarity
from ..models.state_models import RoutingState
import re

# ----------------------------
# 유틸 함수: 플레이스홀더 치환
# ----------------------------
def resolve_placeholders(input_data, context):
    if isinstance(input_data, dict):
        return {
            key: resolve_placeholders(value, context)
            for key, value in input_data.items()
        }
    elif isinstance(input_data, list):
        return [resolve_placeholders(item, context) for item in input_data]
    elif isinstance(input_data, str) and "{{" in input_data:
        return replace_with_context(input_data, context)
    return input_data

def replace_with_context(text, context):
    def replacer(match):
        try:
            table, column = match.group(1).split(".")
        except ValueError:
            return match.group(0)

        for step_result in reversed(context):
            if isinstance(step_result, str):
                try:
                    step_result = json.loads(step_result)
                except:
                    continue

            if isinstance(step_result, list) and step_result and isinstance(step_result[0], dict):
                if column in step_result[0]:
                    return str(step_result[0][column])
            elif isinstance(step_result, dict) and column in step_result:
                return str(step_result[column])

        return match.group(0)

    return re.sub(r"\{\{(.*?)\}\}", replacer, text)

# ----------------------------
# Plan 실행기
# ----------------------------
def execute_plan(state: RoutingState, llm: ChatOpenAI) -> RoutingState:
    message = state.message
    user_type = state.user_type

    try:
        plan_data = json.loads(state.plan)
        # "step-by-step action plan" 키로 접근하는 경우 처리
        if "step-by-step action plan" in plan_data:
            plan = plan_data["step-by-step action plan"]
        else:
            plan = plan_data
    except Exception as e:
        raise ValueError(f"Invalid plan JSON: {e}")

    context = state.context or []
    results = []

    tools_for_member = {
        "web_search": web_search,
        "master_select_db_multi": master_select_db_multi,
        "search_exercise_by_name": search_exercise_by_name,
        "retrieve_exercise_info_by_similarity": retrieve_exercise_info_by_similarity
    }

    tools_for_trainer = {
        "web_search": web_search,
        "master_select_db_multi": master_select_db_multi,
        "search_exercise_by_name": search_exercise_by_name,
        "retrieve_exercise_info_by_similarity": retrieve_exercise_info_by_similarity
    }

    if user_type == "member":
        tools = tools_for_member
    elif user_type == "trainer":
        tools = tools_for_trainer

    for idx, step in enumerate(plan):
        # step이 문자열인 경우 처리
        if isinstance(step, str):
            print(f"\n🔥 STEP {idx+1}: 텍스트 결과 처리")
            print(f"📦 TOOL: 없음 (LLM 지식 사용)")
            result = step
            print("result: ", result)
            
            results.append({
                "step": idx + 1,
                "description": "텍스트 결과 처리",
                "result": result
            })
            context.append(result)
            continue
            
        # 일반적인 객체 처리
        tool_name = step.get("tool")
        raw_input_data = step.get("input", {})
        description = step.get("description", "")

        print(f"\n🔥 STEP {idx+1}: {description}")
        print(f"📦 TOOL: {tool_name if tool_name else '없음 (LLM 지식 사용)'}")

        input_data = resolve_placeholders(raw_input_data, context)

        if not tool_name:
            llm_input = "\n".join([
                f"사용자 질문: {message}",
                f"지금까지 수집된 정보:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
                f"현재 단계 목적:\n{description}"
            ])
            llm_response = llm.invoke([HumanMessage(content=llm_input)])
            result = llm_response.content
            print("result: ", result)
        else:
            tool_func = tools.get(tool_name)

            if not tool_func:
                result = f"[ERROR] 등록되지 않은 tool: {tool_name}"
                print("result: ", result)
            else:
                try:
                    result = tool_func(**input_data)
                    print("result: ", result)
                except Exception as e:
                    result = f"[ERROR during tool execution] {e}"
                    print("result: ", result)

        results.append({
            "step": idx + 1,
            "tool": tool_name,
            "description": description,
            "result": result
        })

        try:
            parsed = json.loads(result) if isinstance(result, str) else result
        except:
            parsed = result

        context.append(parsed)

    state.context = context

    final_llm_input = "\n".join([
        f"사용자 질문: {message}",
        f"지금까지 수집된 정보:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
        f"최종 목적: 위 정보를 바탕으로 사용자가 이해하기 쉽게 정리해서 질문에 답하세요. 단, 질문과 무관한 정보는 제외해야 합니다."
    ])
    final_response = llm.invoke([HumanMessage(content=final_llm_input)])
    final_result = final_response.content

    state.result = final_result
    return state