from typing import List, Dict, Any
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
import json
from ..tools.exercise_routine_tools import master_select_db_multi, web_search
from ..models.state_models import RoutingState
import re

# ----------------------------
# 유틸 함수: 플레이스홀더 치환
# ----------------------------
def resolve_placeholders(input_data, context):
    if isinstance(input_data, dict):
        return {
            key: replace_with_context(value, context) if isinstance(value, str) and "{{" in value else value
            for key, value in input_data.items()
        }
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

    try:
        plan = json.loads(state.plan)
    except Exception as e:
        raise ValueError(f"Invalid plan JSON: {e}")

    context = []
    results = []

    tools = {
        "web_search": web_search,
        "master_select_db_multi": master_select_db_multi,
    }

    for idx, step in enumerate(plan):
        tool_name = step.get("tool")
        raw_input_data = step.get("input", {})
        description = step.get("description", "")

        print(f"\n🔥 STEP {idx+1}: {description}")
        print(f"📦 TOOL: {tool_name if tool_name else '없음 (LLM 지식 사용)'}")

        input_data = resolve_placeholders(raw_input_data, context)

        if not tool_name:
            llm_input = "\n".join([
                f"🗣 사용자 질문: {message}",
                f"📚 지금까지 수집된 정보:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
                f"🎯 현재 단계 목적:\n{description}"
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
            "description": description,
            "result": result
        })

        try:
            parsed = json.loads(result) if isinstance(result, str) else result
        except:
            parsed = result

        context.append(parsed)

    state.context = context
    state.result = results[-1]["result"] if results else "No result"
    return state