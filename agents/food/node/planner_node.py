# planner_node.py
import json
from typing import Any, Dict
from langchain.schema import HumanMessage
from agents.food.tool.recommend_diet_tool import tool_list
from agents.food.llm_config import llm
from agents.food.util.sql_utils import fetch_table_data
from agents.food.util.table_schema import table_schema
from agents.food.agent_state import AgentState

tool_map = {tool.name: tool for tool in tool_list}
def refine_planning_prompt(user_input: str, context: Dict[str, Any], table_schema: Dict[str, Any], tool_map: Dict[str, Any]) -> str:
    tool_names = list(tool_map.keys())
    return f"""
너는 지금 '식단 플래너' 역할이야.
사용자 입력과 context를 분석해서 아래 기준에 따라 실행 계획을 JSON으로 구성해줘.

[💡 핵심 목표]
- 사용자 요청을 해결하기 위해 필요한 정보를 판단하고
- 도구 실행, 질문 생성, SQL 조회 여부 등을 포함한 계획을 수립해줘.
[💡 핵심 원칙]

1. ✅ 식단 추천 요청 시에만 필수 정보(goal, allergies 등)가 없으면 질문을 생성해야 해
    - recommend_diet_tool 실행 시 context 또는 입력에 아래 항목 중 하나라도 없으면 → ask_user 필드에 질문 생성
    - 필수 항목 목록:
        - goal
        - allergies
        - food_preferences
        - food_avoidances
    - 단, 값이 "없음", "없어요", "없습니다" 등으로 명확하게 주어진 경우는 질문 없이 "없음"으로 처리 가능
    - 모호한 응답(예: "잘 모르겠어요", "모름")은 → 질문 유도 대상

2. ✅ 식단 추천 요청이 아닌 다른 요청(record_meal_tool 등)에서는 질문이 절대 발생하면 안 됨
    - 입력에 "먹었", "먹음", "섭취" 등의 키워드가 포함되면 → record_meal_tool 실행
    - 이 경우 필수 정보가 없어도 질문 생성은 ❌ 금지

3. ✅ save_user_goal_and_diet_info 도구는 값이 명시된 경우에만 실행
    - goal, allergies, food_preferences, food_avoidances 중 하나라도 명시된 경우 → save_user_goal_and_diet_info 실행
    - 명시된 값이 하나도 없다면 도구 실행 ❌, 대신 → ask_user 질문을 생성해야 함

4. ✅ "이번주 식단 짜줘"는 과거 기록이 아니라 향후 일주일 식단 추천 요청
    - 이 경우 recommend_diet_tool 실행
    - tool_input에 period = "일주일" 반드시 포함

5. ✅ "오늘 점심 뭐 먹을까?"는 한끼 식단 추천 요청
    - 이 경우 recommend_diet_tool 실행
    - tool_input에 period = "한끼", meal_type = "점심" 포함되어야 함
    - "아침", "저녁"도 동일하게 meal_type 지정
6. **"이번 주 식단 분석해줘"**라는 요청이 들어오면 weekly_average_tool을 사용합니다.
7. **"최근 식사 기록을 TDEE와 비교해줘"**라는 요청이 들어오면 meal_record_gap_report_tool을 사용합니다.
[0. 의도 감지 우선 순위]
- "바나나 먹었어", "점심에 라면 먹음" 같은 입력 → record_meal_tool 실행
- "식단 추천해줘" → recommend_diet_tool 실행
- "다이어트 중이야", "알레르기가 있어" → save_user_goal_and_diet_info 실행
- "요약해줘", "피드백 줘" → summarize_nutrition_tool, diet_feedback_tool 등 실행
- "식사 기록 보여줘", "최근 식단 보여줘", "오늘 먹은 거 알려줘", "이번 주 뭐 먹었어?", "먹은 기록 확인" → get_meal_records_tool 실행
    → get_meal_records_tool 도구를 사용할 경우:
      - tool_input에는 최소한 "member_id"와 "days" 필드를 포함해야 해.
      - days 값이 명시되지 않으면 기본값 7을 넣어줘.
- "내 알레르기 뭐야?", "내 정보 보여줘", "최근 몸무게" 같이 **DB 조회 질문**이면 → sql_query_runner 실행
    - tool_input에는 input 키에 자연어 그대로 전달

[1. 사용자가 goal, allergies, food_preferences, food_avoidances 중 하나라도 명시했으면]
→ save_user_goal_and_diet_info 도구 실행.
→ context에 이미 해당 정보가 있으면 생략 가능.

[1-1. 사용자가 "없어요", "없음", "없습니다" 등 부정 표현을 명확히 언급한 경우]
→ 질문 없이 "없음"으로 저장하고 도구 실행.

📌 예시 입력 → 저장
- "알레르기 없어요" → "allergies": "없음"
- "식사 패턴은 없습니다" → "meal_pattern": "없음"
- "특별히 원하는 음식은 없어요" → "food_preferences": "없음"

📌 예시 입력 → 질문 생성
- "잘 모르겠어요", "생각 안 해봤어요"
[1-2. context의 값이 null이거나, 사용자가 "없어요", "없음" 등을 말한 경우]
→ context가 null이면 질문하지 않고 '없음'으로 저장해야 해.
→ 사용자가 명시적으로 부정 표현을 쓴 경우도 마찬가지야.
→ 저장 시 다음 필드 중 해당되는 것만 포함해:
   - goal
   - allergies
   - food_preferences
   - food_avoidances
[2. 식단 추천 요청 시]
→ 아래 항목 중 하나라도 **context에 null이거나**, 사용자 입력에 명확한 정보가 없다면 질문을 생성해.
→ 단, context 값이 "없음"으로 명시돼 있으면 질문 없이 사용해도 돼.
→ context 값이 null인데 사용자가 "없어요", "없음", "없습니다"라고 말했으면 → "없음"으로 저장하고 질문 없이 도구 실행.
→ context 값이 null이고, 사용자 입력도 없거나 "모르겠어요", "생각 안 해봤어요" 등이면 질문 생성.

→ 추가로, 사용자 입력에 식단 **기간**을 나타내는 표현이 있다면 tool_input에 "period" 필드를 명시해줘야 해.
→ 다음 규칙에 따라 정확한 값을 판단해서 넣어:

- "하루", "1일", "daily" → `"period": "하루"`
- "일주일", "7일", "weekly", "주간" → `"period": "일주일"`
- "한끼", "끼니", "식사", "아침", "점심", "저녁" → `"period": "한끼"`

→ 위 표현이 없거나 모호할 경우 기본값 `"period": "하루"`를 사용해도 돼.

📌 필수 항목 목록:
- goal
- allergies
- food_preferences
- food_avoidances

[3. SQL이 필요한 경우]
- context에 정보가 없을 때 SQL 조회 필요.
- 부족한 테이블은 context_missing 필드에 나열.

[4. 도구 실행]
- 1개의 도구만 실행 (tool_name, tool_input, need_tool: true)

[5. 질문 + 도구 동시 사용 ❌]
- ask_user에 질문이 있으면 도구 관련 필드는 전부 비워야 해.

[6. tool_input은 반드시 JSON 객체여야 해.]

[7. 정보가 충분하면 final_output으로 자연어 응답 작성.]

[8. 외부 지식 필요 시 → web_search_and_summary 도구 실행.]
 
[❗ 반드시 지켜야 할 규칙 ❗]
1. ask_user가 있다면 → 나머지는 비워야 함
2. 도구 실행과 질문은 절대 같이 사용하지 마
3. 출력은 반드시 순수 JSON. ```json 은 ❌
⚠️ 질문이 필요한 경우, 질문은 반드시 ask_user 배열에 넣고, final_output은 비워야 해.
❌ 질문을 final_output에 넣지 마.
✔️ 질문은 각각 독립된 문장으로, 배열 형태로 넣어줘. (예: ["식사 패턴은 어떻게 되시나요?", "활동 수준은 어떤가요?"])
[도구 목록]
{tool_names}

[현재 사용자 입력]
"{user_input}"

[현재 context 정보]
{json.dumps(context, ensure_ascii=False)}

[테이블 스키마 정보]
{json.dumps(table_schema, ensure_ascii=False)}

[출력 예시]

1. ✅ 일반 도구 사용:
{{
  "need_tool": true,
  "tool_name": "record_meal_tool",
  "tool_input": {{
    "member_id": 3,
    "input": "아침에 바나나를 먹었어"
  }},
  "ask_user": [],
  "final_output": "",
  "context_missing": []
}}

2. 📘 get_meal_records_tool 사용:
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

3. ❓ 질문 필요:
{{
  "need_tool": false,
  "tool_name": "",
  "tool_input": {{}},
  "ask_user": ["알레르기가 있으신가요?"],
  "final_output": "",
  "context_missing": []
}}

4. 📄 sql_query_runner 실행:
{{
  "need_tool": true,
  "tool_name": "sql_query_runner",
  "tool_input": {{
    "input": "내 알레르기 정보 알려줘"
  }},
  "ask_user": [],
  "final_output": "",
  "context_missing": []
}}
"""

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

    try:
        parsed = json.loads(response.content.strip())

        # ❌ ask_user와 도구 혼용 금지
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

        # ❌ 금지된 도구 이름
        if parsed.get("tool_name") == "ask_missing_slots":
            return state.copy(update={
                "parsed_plan": {},
                "agent_out": "❌ 질문은 ask_user 로만 넣으세요. 도구 사용 금지!\n\n🔹 원문:\n" + response.content,
                "context": context,
                "tool_result": "",
                "retry_count": 0
            })

        # ❌ tool_input은 반드시 dict여야 함
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
