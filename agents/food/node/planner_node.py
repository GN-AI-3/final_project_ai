import json
from typing import Any, Dict
from langchain.schema import HumanMessage
from  agents.food.tool.recommend_diet_tool import tool_list
from  agents.food.llm_config import llm
from agents.food.util.sql_utils import fetch_table_data
from agents.food.util.table_schema import table_schema
from agents.food.agent_state import AgentState


tool_map = {tool.name: tool for tool in tool_list}
def planner_node(state: AgentState) -> AgentState:
    user_input = state.user_input
    member_id = state.member_id
    context = state.context or {}

    # ✅ context 자동 로딩
    preload_tables = ["member", "member_diet_info", "inbody"]
    for table in preload_tables:
        if table not in context:
            context[table] = fetch_table_data(table, member_id)

    # ✅ 프롬프트 구성
    planning_prompt = refine_planning_prompt(
        user_input=user_input,
        context=context,
        table_schema=table_schema,
        tool_map=tool_map
    )

    # ✅ LLM 호출
    response = llm.invoke([HumanMessage(content=planning_prompt)])

    # ✅ JSON 파싱 및 유효성 검사
    try:
        parsed = json.loads(response.content.strip())

        if parsed.get("ask_user") and (
            parsed.get("need_tool") or parsed.get("tool_name") or parsed.get("final_output")
        ):
            return state.copy(update={
                "parsed_plan": {},
                "agent_out": "❌ ask_user가 있으면 다른 필드를 넣으면 안 돼요!\n\n🔹 원문:\n" + response.content,
                "context": context,
                "tool_result": "",
                "retry_count": 0
            })

        if parsed.get("tool_name") == "ask_missing_slots":
            return state.copy(update={
                "parsed_plan": {},
                "agent_out": "❌ 질문은 ask_user 로만 넣으세요. 도구 사용 금지!\n\n🔹 원문:\n" + response.content,
                "context": context,
                "tool_result": "",
                "retry_count": 0
            })

        if parsed.get("need_tool") and not isinstance(parsed.get("tool_input", {}), dict):
            return state.copy(update={
                "parsed_plan": {},
                "agent_out": f"❌ tool_input은 반드시 JSON 객체여야 해요.\n\n🔹 원문:\n{response.content}",
                "context": context,
                "tool_result": "",
                "retry_count": 0
            })

        return state.copy(update={
            "parsed_plan": parsed,
            "context": context,
            "tool_result": "",
            "retry_count": 0
        })

    except Exception as e:
        return state.copy(update={
            "parsed_plan": {},
            "agent_out": f"❌ LLM 응답 파싱 실패: {e}\n\n🔹 원문:\n{response.content}",
            "context": context,
            "tool_result": "",
            "retry_count": 0
        })



def refine_planning_prompt(user_input: str, context: Dict[str, Any], table_schema: Dict[str, Any], tool_map: Dict[str, Any]) -> str:
    tool_names = list(tool_map.keys())
    return f"""

너는 지금 '식단 플래너' 역할이야.
사용자 입력과 context를 분석해서 아래 기준에 따라 실행 계획을 JSON으로 구성해줘.

[💡 핵심 목표]
- 사용자 요청을 해결하기 위해 필요한 정보를 판단하고
- 도구 실행, 질문 생성, SQL 조회 여부 등을 포함한 계획을 수립해줘.

[0. 의도 감지 우선 순위]
- "바나나 먹었어", "점심에 라면 먹음" 같은 입력 → record_meal_tool 실행
- "식단 추천해줘" → recommend_diet_tool 실행
- "다이어트 중이야", "알레르기가 있어" → save_user_goal_and_diet_info 실행
- "요약해줘", "피드백 줘" → summarize_nutrition_tool, diet_feedback_tool 등 실행
- "식사 기록 보여줘", "최근 식단 보여줘", "오늘 먹은 거 알려줘", "이번 주 뭐 먹었어?", "먹은 기록 확인" → get_meal_records_tool 실행
    → get_meal_records_tool 도구를 사용할 경우:
      - tool_input에는 최소한 "member_id"와 "days" 필드를 포함해야 해.
      - days 값이 명시되지 않으면 기본값 7을 넣어줘.
- 그 외는 context와 도구 목록 기반으로 가장 적절한 도구를 선택해
[1. 사용자가 자연어로 goal, allergies, food_preferences,food_avoidances 중 하나라도 명시했으면]
→ save_user_goal_and_diet_info 도구를 실행해야 해.
→ 단, context에 이미 해당 정보가 있으면 생략해도 돼.

[1-1. 사용자 입력에 "없어요", "없음", "없습니다" 등 부정 표현이 명확하게 포함된 경우]
→ 해당 항목은 '정보 없음'으로 판단하고, 질문 없이 save_user_goal_and_diet_info 도구를 실행해.
→ 예: "알레르기 없어요" → "allergies": "없음" 으로 저장

→ 단, "모르겠어요", "잘 모르겠음", "생각 안 해봤어요" 등과 같은 표현은 정보가 불확실하므로, 해당 항목은 질문을 생성해야 해.

📌 [예시 입력 → 저장 대상]
- "알레르기 없어요" → "allergies": "없음"
- "식사 패턴은 없습니다" → "meal_pattern": "없음"
- "특별히 원하는 음식은 없어요" → "food_preferences": "없음"

📌 [예시 입력 → 질문 생성 대상]
- "잘 모르겠어요"
- "생각 안 해봤는데요"
→ 이 경우는 ask_user에 질문을 넣어줘.

⚠️ 사용자가 "없어요"라고 말하면 반드시 "없음"으로 저장해야 해.  
모호하지 않게, 판단을 망설이지 말고 명확히 처리해줘.

[2. 사용자가 "식단 추천"을 요청했을 경우 (예: "식단 추천해줘", "다이어트 식단 알려줘" 등)]

→ 아래 정보 중 하나라도 context 또는 입력에 없으면 질문 생성
   - goal
   - allergies
   - food_preferences
   - food_avoidances
→ 이 경우에는 ask_user 필드에 질문을 넣고,
→ need_tool, tool_name, final_output은 모두 비워야 해.
[3. SQL이 필요한 경우]
- context에 데이터가 부족하면 "SQL 조회 필요"라고 판단한 후
- 해당 정보가 부족하다고 판단되는 테이블명을 tool_input.context_missing 필드에 넣어줘
예시: "context_missing": ["inbody", "member_diet_info"]

[4. 도구 실행 판단]
- 아래 도구 목록 중에서 가장 적절한 1개의 도구만 선택해서 실행
- 도구 이름은 tool_name, 입력은 tool_input에 명시
- need_tool은 항상 true로 설정

[5. 질문 + 도구 동시 금지 ❌]
- ask_user에 질문이 있다면, 나머지 필드(도구 관련)는 전부 비워야 해.

[6. tool_input은 반드시 JSON 객체로 구성해야 해.]

[7. 정보가 충분해서 바로 응답할 수 있다면]
- final_output 필드에 사용자에게 보여줄 자연어 답변을 작성해줘.

[8. 모르는건 웹 검색을 수행해]
- 모르는건 웹 검색을 수행해.
- 웹 검색 결과는 web_search_and_summary 도구를 실행해.
- 웹 검색 결과는 최대 3개까지만 보여줘.

[❗❗ 절대 규칙 – 반드시 지켜야 해! ❗❗]

1. ask_user에 질문이 **하나라도** 있으면:
   → need_tool, tool_name, tool_input, final_output은 **전부 비워야 해!**

2. 질문을 도구로 해결하려고 하지 마라.
   ❌ ask_missing_slots, ❌ search_tool, ❌ any other tool — 전부 금지!

3. 도구 실행과 질문은 **동시에 절대 하지 마!**
   → ask_user는 질문용 전용 필드야. 도구는 다른 상황에서만 써야 해.

[도구 목록]
{tool_names}

[현재 사용자 입력]
"{user_input}"

[현재 context 정보]
{json.dumps(context, ensure_ascii=False)}

[테이블 스키마 정보]
{json.dumps(table_schema, ensure_ascii=False)}
[출력 형식 예시 – 반드시 아래 JSON 중 하나로만 출력하세요]

1. ✅ 일반적인 도구 실행을 해야 할 경우:
예: record_meal_tool, recommend_diet_tool 등
{{
  "need_tool": true,
  "tool_name": "record_meal_tool",
  "tool_input": {{
    "member_id": 3,
    "input": "아침에 바나나를 먹었어",
    "meal_type": "아침"
  }},
  "ask_user": [],
  "final_output": "",
  "context_missing": []
}}

2. 📘 도구 get_meal_records_tool를 사용시에만 아래 출력 형식을 사용해:
{{
  "need_tool": true,
  "tool_name": "get_meal_records_tool",
  "tool_input": {{
    "member_id": 3,
    "days": 7
  }},
  "ask_user": [],
  "final_output": "",
  "context_missing": []
}}

3. ❓ 사용자에게 질문이 필요한 경우:
{{
  "need_tool": false,
  "tool_name": "",
  "tool_input": {{}},
  "ask_user": [
    "당신의 목표가 무엇인가요?",
    "알레르기가 있으신가요?"
  ],
  "final_output": "",
  "context_missing": []
}}

⚠️ 출력은 반드시 **순수 JSON** 형식으로만 출력해줘.  
❌ 절대로 ```json ...``` 또는 설명 문장을 포함하지 마!
"""
