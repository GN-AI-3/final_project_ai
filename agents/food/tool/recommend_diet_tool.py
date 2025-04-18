# tools/tool_list.py

# 도구 이름                        | 설명
# ------------------------------|-------------------------------------------------------------
# record_meal_tool              | 자연어 식사 입력을 파싱 → 영양정보 조회 → meal_records 저장
# search_food_tool             | ElasticSearch 기반 음식명 자동완성 및 유사 영양정보 조회
# general_result_validator     | 도구 실행 결과의 유효성과 적합성 평가 (LLM 기반)
# caloric_target_tool          | TDEE 기반 목표별 칼로리 타겟 계산 (다이어트/유지/벌크업)
# nutrition_gap_feedback_tool  | 총 섭취 칼로리 vs TDEE 비교 피드백 제공
# meal_record_gap_report_tool | 최근 섭취 기록 기반 영양소 과부족 리포트 생성
# auto_tdee_wrapper            | 사용자 정보 자동 조회 후 TDEE 계산 실행
# tdee_calculator_tool         | 직접 전달된 정보 기반으로 TDEE 계산 수행
# nutrition_goal_gap_tool      | 식단 요약 정보와 목표 비교하여 과부족 분석
# diet_explanation_tool        | 추천 식단 구성 이유를 자연어 설명으로 생성
# save_recommended_diet        | JSON 식단 결과를 DB(recommended_diet_plans)에 저장
# recommend_food_tool          | 사용자 알레르기/선호 기반 음식 추천
# recommend_diet_tool          | 사용자 목표 기반 하루/주간 식단 추천 + 요약 포함
# sql_query_runner             | 자연어 기반 SQL SELECT 자동 생성 및 실행
# sql_insert_runner            | 자연어 기반 SQL INSERT 자동 생성 및 실행
# ask_missing_slots            | 누락된 슬롯(정보)을 자동으로 질문 리스트로 반환
# search_food_nutrition        | Tavily 기반 음식 영양 정보 검색
# lookup_nutrition_tool        | 음식명 기반으로 ES → DB → Tavily + LLM 추론 순 조회
# validate_result_tool         | 도구 실행 결과가 충분한지 판단하는 LLM 평가 도구
# diet_feedback_tool           | 추천 식단이 목표에 적합한지 피드백 제공
# summarize_nutrition_tool     | 식단 요약(JSON) → 총 칼로리/영양소 정리
# weekly_average_tool          | 식단의 주간 평균 영양소 계산
# user_profile_tool            | member_id 기반 사용자 건강 정보 종합 조회
# meal_parser_tool             | 자연어 식사 입력 → 음식명/양/단위/끼니 파싱
# save_user_goal_and_diet_info | 자연어로부터 사용자 식단 정보 추출 및 DB 저장


from datetime import datetime
import json
import re
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from langchain_community.retrievers import TavilySearchAPIRetriever
from  agents.food.util.table_schema import table_schema
from  agents.food.llm_config import llm
import psycopg2
import traceback
from elasticsearch import Elasticsearch
import requests
import os
load_dotenv() 
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
def call_spring_api(endpoint: str, data: dict, method: str = "POST") -> dict:
    """
    스프링 부트 API를 호출하는 함수
    - method: "POST" 또는 "PUT"
    - JWT 토큰은 기본값 또는 환경 변수에서 로드
    """
    base_url = "http://localhost:8081"
    url = f"{base_url}{endpoint}"

    # 🔐 JWT 토큰: 환경 변수 또는 기본값 사용
    AUTH_TOKEN = os.getenv(
        "AUTH_TOKEN",
        "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsInBob25lIjoiMDEwMTExMTIyMjIiLCJuYW1lIjoi7J6l6re87JqwIiwiaWQiOjQsInVzZXJUeXBlIjoiTUVNQkVSIiwiZW1haWwiOiJ1c2VyMUB0ZXN0LmNvbSIsImdvYWxzIjpbIldFSUdIVF9MT1NTIl0sImlhdCI6MTc0NDc4NjAxNiwiZXhwIjoxNzQ1MTQ2MDE2fQ.K0hNJEV0TLj0qYdFGpP0KeowQHmZ7kWwzxN_c8gMekjVbb1KnvMiJ0YHhsHLYG49"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    print(f"🔍 호출 URL: {url}")
    print(f"🔍 헤더: {headers}")
    print(f"🔍 데이터: {data}")
    try:
        method = method.upper()
        if method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            return {"error": f"지원하지 않는 HTTP 메서드: {method}"}

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"API 호출 실패: {str(e)}"}

es = Elasticsearch("http://localhost:9200")
pg_conn = psycopg2.connect(
    host="3.37.8.185",
    port=5433,
    dbname="gym",
    user="postgres",
    password="1234"
)
pg_cur = pg_conn.cursor()
# 실제 DB 실행 유틸 (psycopg2 기반)
def execute_sql(query: str) -> str:
    import json
    from datetime import datetime, date
    import psycopg2

    def serialize(obj):
        import datetime
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, datetime.time):  # ✅ 이 부분 꼭 추가!
            return obj.strftime("%H:%M:%S")
        raise TypeError(f"Type {type(obj)} not serializable")


    try:
        conn = psycopg2.connect(
            host="3.37.8.185",
            port=5433,
            dbname="gym",
            user="postgres",
            password="1234"
        )
        cur = conn.cursor()
        cur.execute(query)

        if query.strip().lower().startswith("select"):
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            data = [dict(zip(columns, row)) for row in rows]
            result = json.dumps(data, default=serialize, ensure_ascii=False, indent=2)
        else:
            conn.commit()
            result = json.dumps({"status": "✅ SQL 실행 완료"}, ensure_ascii=False)

        cur.close()
        conn.close()
        return result

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "❌ SQL 실행 오류",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, ensure_ascii=False)



@tool
def web_search_and_summary(params: dict) -> str:
    """모르는건 웹 검색을 수행합니다."""
    query = params.get("user_input", "")
    retriever = TavilySearchAPIRetriever(k=3, tavily_api_key=TAVILY_API_KEY)

    docs = retriever.invoke(query)

    prompt = PromptTemplate.from_template("""
    다음은 웹에서 검색한 결과입니다.
    질문: {query}
    문서: {docs}

    이 정보를 요약해줘.
    """)
    prompt_text = prompt.format(query=query, docs=docs)
    return llm.invoke([HumanMessage(content=prompt_text)]).content.strip()



@tool
def sql_query_runner(params: dict) -> str:
    """자연어 입력을 기반으로 SQL SELECT 쿼리를 생성하고 실행합니다."""

    sql = generate_sql(params.get("input", ""))
    result = execute_sql(sql)
    return f"[SQL 실행 결과]\nSQL: {sql}\n결과: {result}"

@tool
def sql_insert_runner(params: str) -> str:
    """사용자의 요청을 기반으로 SQL INSERT 쿼리를 생성하고 실행합니다."""
    sql = generate_sql(params + " (insert 쿼리 형식으로)")
    result = execute_sql(sql)
    return f"[INSERT 실행 결과]\nSQL: {sql}\n결과: {result}"

def extract_json_from_response(text: str) -> str:
    """
    LLM 응답에서 ```json ... ``` 블록을 제거하고 JSON 텍스트만 추출
    """
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()

def strip_code_block(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)  # ✅ 올바른 정규식
    return match.group(1).strip() if match else text.strip()

@tool
def save_user_goal_and_diet_info(params: dict) -> str:
    """
    자연어 입력에서 사용자 식단에 필요한 정보를 추출하고 DB에 자동 저장합니다.
    """

    def extract_json_string(text: str) -> str:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        if text.strip().startswith("{"):
            return text.strip()
        return ""

    def check_diet_info_exists(member_id: int) -> bool:
        query = f"SELECT 1 FROM member_diet_info WHERE member_id = {member_id} LIMIT 1;"
        try:
            result = execute_sql(query)
            print(f"🔍 member_diet_info 존재 여부 조회 결과: {result}")
            return bool(result)
        except Exception as e:
            print(f"❌ DB 조회 실패: {e}")
            return False

    try:
        user_input = params.get("input", "")
        member_id = params.get("member_id", 1)

        print(f"\n👤 사용자 입력: {user_input}")
        print(f"👤 member_id: {member_id}")

        extract_prompt = f"""
        다음은 사용자의 자연어 입력이야. goal, gender, allergies 등의 정보를 추출해서 JSON으로 정리해줘.
        누락된 값은 빈 문자열("")로 표시하고, 아래 형식을 지켜줘.

        [입력]
        {user_input}

        [출력 형식]
        {{
          "goal": "...",
          "gender": "...",
          "allergies": "...",
          "food_preferences": "...",
          "meal_pattern": "...",
          "activity_level": "...",
          "special_requirements": "...",
          "food_avoidances": "..."
        }}
        """
        response = llm.invoke([HumanMessage(content=extract_prompt)])
        raw_response = response.content.strip()
        print(f"\n🧠 LLM 응답:\n{raw_response}")

        if not raw_response:
            return "❌ LLM 응답이 비어 있습니다."

        json_str = extract_json_string(raw_response)
        print(f"\n📦 추출된 JSON 문자열:\n{json_str}")

        try:
            parsed = json.loads(json_str)
        except Exception as e:
            return f"❌ JSON 파싱 실패: {e}\n\n[응답 내용]\n{raw_response}"

        print(f"\n✅ 파싱된 결과:\n{json.dumps(parsed, indent=2, ensure_ascii=False)}")

        # member 업데이트
        if parsed.get("goal") or parsed.get("gender"):
            member_data = {
                "memberId": member_id,
                "goal": parsed.get("goal", "")
            }
            print(f"\n📤 member 업데이트 요청: {member_data}")
            member_result = call_spring_api("/api/member/update", member_data, method="PUT")
            print(f"✅ member API 응답: {member_result}")

        # diet_info 저장
        if any([
            parsed.get("allergies"),
            parsed.get("food_preferences"),
            parsed.get("meal_pattern"),
            parsed.get("activity_level"),
            parsed.get("special_requirements")
        ]):
            diet_info_data = {
                "memberId": member_id,
                "allergies": parsed.get("allergies", ""),
                "foodPreferences": parsed.get("food_preferences", ""),
                "mealPattern": parsed.get("meal_pattern", ""),
                "activityLevel": parsed.get("activity_level", ""),
                "specialRequirements": parsed.get("special_requirements", "")
            }
            method = "PUT" if check_diet_info_exists(member_id) else "POST"
            print(f"\n📤 diet_info {method} 요청: {diet_info_data}")
            result = call_spring_api("/api/food/user/diet-info"+"", diet_info_data, method=method)
            print(f"✅ diet_info API 응답: {result}")
            if "error" in result:
                return f"❌ 식단 정보 저장 실패: {result['error']}"

        return f"✅ 사용자 식단 정보 저장 완료\n\n{json.dumps(parsed, indent=2, ensure_ascii=False)}"

    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"



# ✅ datetime 직렬화 핸들러
def safe_json(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")
@tool
def lookup_nutrition_tool(params: dict) -> str:
    """
    음식 이름에 기반하여 영양 정보를 조회합니다.
    - Step 1: ElasticSearch에서 유사 이름 검색 (자동완성 + 오타 허용)
    - Step 2: PostgreSQL에서 ID 기반 영양정보 조회
    - Step 3: 없으면 → Tavily + LLM 추론 (DB/ES 저장은 ❌)
    """
    import json
    import traceback
    
    food_name = params.get("user_input", "").strip() 
    print(f"🔍 음식 이름: {food_name}")
    food_name = params.get("food_name") or params.get("user_input") or params.get("input", "")
    food_name = food_name.strip()

    print(f"🔍 음식 이름: {food_name}")
    if not food_name:
        return "❌ 음식 이름이 제공되지 않았습니다."
    try:
        # Step 1: Elasticsearch 검색
        es_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"name": {"query": food_name, "fuzziness": "AUTO"}}},
                        {"match_phrase_prefix": {"name": {"query": food_name}}}
                    ]
                }
            }
        }

        results = es.search(index="food_nutrition_index", query=es_query["query"])
        hits = results["hits"]["hits"]

        if hits:
            food_id = hits[0]["_source"]["id"]
            pg_cur.execute("SELECT * FROM food_nutrition WHERE id = %s", (food_id,))
            row = pg_cur.fetchone()
            if row:
                columns = [desc[0] for desc in pg_cur.description]
                food_dict = dict(zip(columns, row))

                # datetime → str 변환
                for k, v in food_dict.items():
                    if hasattr(v, 'isoformat'):
                        food_dict[k] = v.isoformat()

                return json.dumps(food_dict, ensure_ascii=False, indent=2)

        # Step 3: Tavily + LLM 추론
        retriever = TavilySearchAPIRetriever(k=3, tavily_api_key=TAVILY_API_KEY)
        info = retriever.invoke(f"{food_name} 100g 영양성분")

        prompt = PromptTemplate.from_template("""\
아래 문서에서 "{food_name} 100g" 기준으로
칼로리, 단백질, 지방, 탄수화물 수치를 JSON으로 정리해줘.

예시:
{{
  "food_item_name": "{food_name}",
  "calories": ..., "protein": ..., "fat": ..., "carbs": ...
}}

문서:
{info}
""")
        formatted_prompt = prompt.format(food_name=food_name, info=info)
        response = llm.invoke([HumanMessage(content=formatted_prompt)])

        return extract_json_block(response.content.strip())

    except Exception as e:
        return f"❌ lookup 실패: {str(e)}\n{traceback.format_exc()}"

ask_prompt = PromptTemplate.from_template("""
너는 대화 시스템의 슬롯 채우기 보조자야.
아래 사용자 요청을 보고 부족한 정보가 무엇인지 질문 리스트를 만들어줘.

- 테이블 스키마:
{schema_text}

- 사용자 요청:
{user_input}

결과 형식:
[
  "질문1",
  "질문2"
]
""")

@tool
def ask_missing_slots(params: dict) -> str:
    """사용자의 요청에서 누락된 정보를 질문 리스트로 반환합니다."""
    prompt = ask_prompt.format(user_input=params.get("user_input", ""), schema_text=table_schema)
    messages = [HumanMessage(content=prompt)]
    response = llm(messages)
    return response.content.strip()



SQL_PROMPT = PromptTemplate.from_template("""
너는 SQL 전문가야. 사용자의 자연어 요청을 분석해 아래 스키마를 바탕으로 정확한 SQL 쿼리를 작성해.

[테이블 스키마]
{schema_text}

[사용자 요청]
{user_input}

-- 다음 조건을 반드시 지켜라:
- 반드시 SQL만 출력하고 설명은 금지한다.
- SELECT/INSERT/UPDATE 등 적절한 쿼리를 생성해라.
- 테이블 이름과 컬럼명을 반드시 일치시켜라.

[출력 형식 예시]
SELECT * FROM ... WHERE ...;
""")



def generate_sql(user_input: str) -> str:
    prompt = SQL_PROMPT.format(schema_text=table_schema, user_input=user_input)
    messages = [HumanMessage(content=prompt)]
    response = llm(messages)
    return response.content.strip()

@tool
def recommend_food_tool(params: dict) -> str:
    """
    사용자의 식단 선호와 알레르기 정보를 기반으로 개인화된 음식 추천을 제공합니다.
    """

    member_id = params.get("member_id")
    prompt = f"""
    사용자 ID {member_id}의 선호도 및 알레르기 정보를 기반으로
    하루 식사에 어울릴 만한 건강하고 균형 잡힌 음식 3~5개를 추천해줘.
    포맷:
    - 음식명: 간단한 설명
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
@tool
def recommend_diet_tool(params: dict) -> str:
    """
    사용자 ID에 기반해 개인 맞춤 식단을 추천합니다.
    goal, gender, allergies, special_requirements 등을 반영합니다.
    """
    def normalize(val: str, fallback: str = "없음"):
        return val if val and str(val).lower() not in ["null", "none"] else fallback

    def standardize_period(raw_period: str) -> str:
        raw = raw_period.strip().lower()
        if raw in ["하루", "1일", "daily"]: return "하루"
        if raw in ["일주일", "7일", "weekly"]: return "일주일"
        if raw in ["한끼", "끼니", "식사", "아침", "점심", "저녁"]: return "한끼"
        return "하루"

    def extract_json_block(text: str) -> str:
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        elif "{" in text and "}" in text:
            try:
                return text[text.index("{"):text.rindex("}") + 1]
            except:
                return text
        return text

    # ✅ 사용자 정보 파싱
    member_id = params.get("member_id", 1)
    raw_period = params.get("period") or params.get("meal_type") or "하루"
    period = standardize_period(raw_period)

    context = params.get("context", {})
    member_info = context.get("member", {})
    diet_info = context.get("user_diet_info", {})

    goal = normalize(member_info.get("goal"))
    gender = normalize(member_info.get("gender"), "F")
    special = normalize(diet_info.get("special_requirements"))
    allergies = normalize(diet_info.get("allergies"))
    preferences = normalize(diet_info.get("food_preferences"))
    pattern = normalize(diet_info.get("meal_pattern"))
    avoidances = normalize(diet_info.get("food_avoidances"))
    # ✅ 식단 예시 조회
    example_sql = f"""
    SELECT breakfast, lunch, dinner
    FROM diet_plans
    WHERE diet_type ILIKE '%{goal}%'
    AND user_gender = '{gender}'
    LIMIT 3;
    """
    example_data = execute_sql(example_sql)

    # ✅ 포맷 지정
    if period == "하루":
        plan_format = '''"monday": {"아침": "...", "점심": "...", "저녁": "..."}'''
    elif period == "일주일":
        plan_format = '''"monday": {"아침": "...", "점심": "...", "저녁": "..."}, "tuesday": {...}, ...'''
    elif period == "한끼":
        plan_format = '''"meal": "..."'''
    else:
        plan_format = '''"monday": {"아침": "...", "점심": "...", "저녁": "..."}'''

    # ✅ 프롬프트 구성
    prompt = f"""
    한국 사용자에게 맞춤 식단을 {period} 기준으로 추천해줘.

    [사용자 정보]
    - 목표: {goal}
    - 성별: {gender}
    - 기타 사항: {special}
    - 알레르기: {allergies}
    - 음식 기호: {preferences}
    - 식사 패턴: {pattern}
    - 거부 음식: {avoidances}
    [식단 예시]
    {example_data}

    출력 형식(JSON):
    {{
      "scope": "{period}",
      "plan": {{
        {plan_format}
      }},
      "summary": {{
        "총칼로리": "...",
        "단백질": "...",
        "탄수화물": "...",
        "지방": "..."
      }},
      "comment": "추천 이유 및 주의사항"
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    plan_result = response.content.strip()

    # ✅ 후처리 (파싱 및 보완)
    try:
        raw_json = extract_json_block(plan_result)
        plan_json = json.loads(raw_json)
        json_text = extract_json_block(plan_result)

        # 🔎 요약 계산
        summary = summarize_nutrition_tool.invoke({
            "params": {
                "user_input": json_text
            }
        })
        plan_json["summary"] = json.loads(summary)

        # 💬 피드백
        feedback = diet_feedback_tool.invoke({
            "params": {
                "input": extract_json_block(plan_result),
                "member_id": member_id,
                "goal": goal
            }
        })
        plan_json["feedback"] = json.loads(feedback)

        return json.dumps(plan_json, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ 응답 파싱 실패 또는 LLM 출력 오류\n\n{plan_result}\n\n📛 오류: {str(e)}"

@tool
def validate_result_tool(params: dict) -> str:
    """
    도구 실행 결과가 충분한지 판단하고, 개선이 필요한지 LLM이 검토함.
    """
    result = params.get("user_input", "")
    intent = params.get("intent", "")
    member_id = params.get("member_id", 1)

    prompt = f"""
    아래는 사용자의 요청({intent})에 대한 추천 결과야.  
    사용자의 목표는 '건강한 식단', ID는 {member_id}라고 가정해.

    이 결과가 식단적으로나 구성상으로 충분한지 판단해줘.
    - 기준: 다양성, 칼로리 균형, 음식 구성, 사용자 목표 부합 여부
    - 너무 단조롭거나 부적절하다면 다시 추천해야 해

    [추천 결과]
    {result}

    출력 포맷:
    {{
      "valid": true/false,
      "reason": "왜 그런 판단을 했는지",
      "suggestion": "불충분 시 어떤 개선이 필요한지"
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
@tool
def summarize_nutrition_tool(params: dict) -> str:
    """
    추천 식단(JSON) 기반으로 총 영양소 요약 계산
    """
    import json
    import re

    try:
        plan_data = json.loads(params.get("user_input", ""))
        plan = plan_data.get("plan", {})

        total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

        # 각 요일/끼니 순회
        for day in plan.values():
            for meal_text in day.values():
                if not isinstance(meal_text, str):
                    continue

                # kcal 감지
                cal_match = re.findall(r"(\d+)\s*(?:kcal|칼로리)", meal_text)
                for match in cal_match:
                    total["calories"] += int(match)

                # 단백질/탄수화물/지방 패턴 감지
                prot_match = re.findall(r"단백질\s*(\d+)\s*(?:g)?", meal_text)
                carb_match = re.findall(r"탄수화물\s*(\d+)\s*(?:g)?", meal_text)
                fat_match = re.findall(r"지방\s*(\d+)\s*(?:g)?", meal_text)

                total["protein"] += sum(int(x) for x in prot_match)
                total["carbs"] += sum(int(x) for x in carb_match)
                total["fat"] += sum(int(x) for x in fat_match)

        return json.dumps({
            "총칼로리": f"{total['calories']} kcal",
            "단백질": f"{total['protein']} g",
            "탄수화물": f"{total['carbs']} g",
            "지방": f"{total['fat']} g"
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "총칼로리": "0 kcal",
            "단백질": "0 g",
            "탄수화물": "0 g",
            "지방": "0 g",
            "error": f"❌ 요약 실패: {e}"
        }, ensure_ascii=False)


@tool
def weekly_average_tool(params: dict) -> str:
    """
    일주일 식단의 평균 영양소 요약
    """
    import json
    try:
        plan = json.loads(params.get("user_input", "")).get("plan", {})
        total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        day_count = 0

        for day in plan.values():
            day_count += 1
            # 예: 하루 요약이 이미 있는 경우 활용 가능

        return json.dumps({
            "요일 수": day_count,
            "평균 칼로리": f"{total['calories'] // max(day_count, 1)} kcal",
            "평균 단백질": f"{total['protein'] // max(day_count, 1)} g",
            "평균 탄수화물": f"{total['carbs'] // max(day_count, 1)} g",
            "평균 지방": f"{total['fat'] // max(day_count, 1)} g",
        }, ensure_ascii=False)
    except Exception as e:
        return f"❌ 평균 분석 실패: {e}"
@tool
def diet_feedback_tool(params: dict) -> str:
    """
    추천 식단 결과가 사용자에게 적합한지 평가 (LLM 기반)
    """
    from langchain.schema import HumanMessage
    input_text = params.get("input", "")
    member_id = params.get("member_id", 1)
    goal = params.get("goal", "건강한 식단")

    prompt = f"""
    아래는 사용자 ID {member_id}의 추천 식단 결과야.
    목표는 '{goal}'이고, 식단의 구성, 균형, 다양성 측면에서 적절한지 평가해줘.

    [식단 결과]
    {input_text}

    출력 포맷 예시:
    {{
      "valid": true,
      "reason": "균형 잡힌 식사이며 목표에 적합",
      "suggestion": ""
    }}

    또는:

    {{
      "valid": false,
      "reason": "아침 메뉴가 너무 단조롭습니다",
      "suggestion": "아침에 단백질과 과일 추가"
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()

    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "valid": False,
            "reason": "응답이 JSON 형식이 아님",
            "suggestion": "출력 포맷을 다시 확인해줘",
            "raw": raw
        }, ensure_ascii=False, indent=2)

 
@tool
def user_profile_tool(params: dict) -> str:
    """
    member_id 기반으로 사용자 건강/선호 정보를 요약해서 반환합니다.
    - member + member_diet_info + inbody 기반
    """
 
    member_id = params.get("member_id", 1)

    query = f"""
    SELECT m.name, m.goal, m.gender,
           d.special_requirements, d.food_preferences, d.allergies,d.food_avoidances
           i.weight, i.height, i.bmi
    FROM member m
    LEFT JOIN member_diet_info d ON m.member_id = d.member_id
    LEFT JOIN inbody i ON m.member_id = i.member_id
    WHERE m.member_id = {member_id}
    ORDER BY i.date DESC NULLS LAST
    LIMIT 1;
    """
    return execute_sql(query)

@tool
def meal_parser_tool(params: dict) -> str:
    """
    자연어 식사 기록에서 음식명, 양, 단위, 식사 시간/끼니 분류 등을 추출합니다.
    예: "점심에 고구마 150g 먹었어"
    """
    print(f"✅식사 추출출 입력 파라미터: {params}")

    input_text = params.get("user_input", "")
    prompt = f"""
    다음 문장에서 식사 기록 정보를 JSON으로 추출해줘.

    입력:
    {input_text}

    출력 형식 예시:
    {{
      "meal_type": "점심",
      "food_name": "고구마",
      "portion": 150,
      "unit": "g"
    }}
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
 
@tool
def save_recommended_diet(params: dict) -> str:
    """
    추천된 식단(JSON)을 recommended_diet_plans 테이블에 저장
    """
    import json
    plan = json.loads(params.get("user_input", "{}"))
    member_id = params.get("member_id", 1)

    day = plan.get("scope", "daily")
    plan_json = plan.get("plan", {})
    summary = plan.get("summary", {})
    comment = plan.get("comment", "")

    try:
        sql = f"""
        INSERT INTO recommended_diet_plans (member_id, plan_scope, plan_summary, breakfast_plan, lunch_plan, dinner_plan)
        VALUES (
            {member_id},
            '{day}',
            '{comment}',
            '{plan_json.get('monday', {}).get("아침", "")}',
            '{plan_json.get('monday', {}).get("점심", "")}',
            '{plan_json.get('monday', {}).get("저녁", "")}'
        )
        """
        return execute_sql(sql)
    except Exception as e:
        return f"❌ 저장 실패: {e}"

@tool
def diet_explanation_tool(params: dict) -> str:
    """
    추천 식단의 이유와 구성 설명을 LLM으로 생성
    """
    from langchain.schema import HumanMessage
    diet_plan = params.get("user_input", "")
    prompt = f"""
    아래 식단은 사용자의 건강 목표에 맞춰 추천된 것이야.
    식단 내용을 분석하고 왜 이렇게 구성되었는지 간단히 설명해줘.

    식단 내용:
    {diet_plan}
    """
    return llm.invoke([HumanMessage(content=prompt)]).content.strip()

@tool
def nutrition_goal_gap_tool(params: dict) -> str:
    """
    사용자 목표 기준과 비교한 영양소 과부족 분석
    """
    from langchain.schema import HumanMessage
    summary = params.get("user_input", "")
    goal = params.get("goal", "다이어트")

    prompt = f"""
    다음은 추천 식단의 요약이야.
    사용자 목표는 '{goal}'인데, 이 식단이 영양소 기준에서 어떤 부분이 부족하거나 과잉인지 분석해줘.

    요약 정보:
    {summary}
    """
    return llm.invoke([HumanMessage(content=prompt)]).content.strip()

@tool
def tdee_calculator_tool(params: dict) -> str:
    """
    사용자 인바디 정보 + 활동량을 기반으로 TDEE (총 에너지 소비량)를 계산합니다.
    """
    try:
        weight = float(params.get("weight", 0))
        height = float(params.get("height", 0))
        age = int(params.get("age", 25))  # 기본 25세
        gender = params.get("gender", "female")
        activity_level = params.get("activity_level", "moderate")  # low, moderate, high

        if not (weight and height):
            return "❌ 체중과 키 정보가 필요합니다."

        # BMR 계산
        if gender.lower() == "M":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        # 활동 계수 적용
        activity_factors = {
            "low": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        factor = activity_factors.get(activity_level, 1.55)
        tdee = round(bmr * factor)

        return f"TDEE 추정치는 약 {tdee} kcal/day 입니다. (BMR: {round(bmr)} × 활동계수: {factor})"

    except Exception as e:
        return f"❌ TDEE 계산 실패: {e}"

@tool
def auto_tdee_wrapper(params: dict) -> str:
    """
    사용자 정보를 자동 추출하고 TDEE 계산을 수행합니다.
    """
    import json

    member_id = params.get("member_id", 1)
    query = f"""
    SELECT m.gender, m.name, d.activity_level, i.weight, i.height
    FROM member m
    LEFT JOIN user_diet_info d ON m.member_id = d.member_id
    LEFT JOIN inbody i ON m.member_id = i.member_id
    WHERE m.member_id = {member_id}
    ORDER BY i.date DESC NULLS LAST
    LIMIT 1;
    """
    result = execute_sql(query)
    if "error" in result or "[]" in result:
        return "❌ 사용자 건강 정보 없음"

    try:
        data = json.loads(result)[0]
        return tdee_calculator_tool.invoke({
            "weight": data.get("weight"),
            "height": data.get("height"),
            "gender": data.get("gender"),
            "activity_level": data.get("activity_level", "moderate"),
            "age": params.get("age", 30)  # 나이 수동 or 추론 필요
        })
    except Exception as e:
        return f"❌ 자동 TDEE 계산 실패: {e}"

@tool
def caloric_target_tool(params: dict) -> str:
    """
    TDEE를 기반으로 다이어트/유지/벌크업 목표별 칼로리 섭취 타겟 계산
    """
    try:
        tdee = float(params.get("tdee", 2000))

        return {
            "다이어트_타겟": f"{int(tdee * 0.8)} kcal",
            "유지_타겟": f"{int(tdee)} kcal",
            "벌크업_타겟": f"{int(tdee * 1.2)} kcal"
        }
    except Exception as e:
        return f"❌ 타겟 칼로리 계산 실패: {e}"

@tool
def nutrition_gap_feedback_tool(params: dict) -> str:
    """
    추천 식단 or 식사 기록의 총 칼로리와 TDEE를 비교해 피드백 제공
    """
    import json

    try:
        tdee = float(params.get("tdee", 2000))
        diet_summary = json.loads(params.get("summary", "{}"))
        total_calories = int(diet_summary.get("총칼로리", "0").replace("kcal", "").strip())

        diff = total_calories - tdee
        status = "적정" if abs(diff) < 150 else ("과다섭취" if diff > 0 else "부족섭취")

        return json.dumps({
            "TDEE": f"{int(tdee)} kcal",
            "섭취량": f"{total_calories} kcal",
            "차이": f"{diff} kcal",
            "판단": status
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ 비교 실패: {e}"

@tool
def meal_record_gap_report_tool(params: dict) -> str:
    """
    최근 식사 기록 기반으로 총 섭취량을 계산하고, TDEE와 비교하여 과부족 여부 리포트.
    입력: {"member_id": 1, "tdee": 2200, "days": 1}
    """
    member_id = params.get("member_id", 1)
    tdee = float(params.get("tdee", 2000))
    days = int(params.get("days", 1))

    sql = f"""
    SELECT meal_type, calories, protein, carbs, fat, meal_date
    FROM meal_records
    WHERE member_id = {member_id}
    AND meal_date >= CURRENT_DATE - INTERVAL '{days} days';
    """

    try:
        raw = execute_sql(sql)
        records = json.loads(raw if isinstance(raw, str) else str(raw))

        total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        for r in records:
            total["calories"] += int(r.get("calories", 0))
            total["protein"] += float(r.get("protein", 0))
            total["carbs"] += float(r.get("carbs", 0))
            total["fat"] += float(r.get("fat", 0))

        diff = total["calories"] - tdee
        status = "정상범위" if abs(diff) < 150 else ("과다섭취" if diff > 0 else "부족섭취")

        return json.dumps({
            "분석일수": days,
            "섭취 총합": total,
            "TDEE": f"{int(tdee)} kcal",
            "칼로리 차이": f"{diff:+} kcal",
            "판단": status
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ 분석 실패: {e}"

@tool
def general_result_validator(params: dict) -> str:
    """
    사용자 요청 + 도구 결과 + context 기반으로 결과의 유효성/적합성 평가
    """
    user_input = params.get("user_input", "")
    tool_result = params.get("result", "")
    context = params.get("context", {})
    tool_name = params.get("tool_name", "")

    prompt = f"""
    다음은 사용자 요청과 도구 실행 결과야.

    [요청]
    {user_input}

    [도구 이름]
    {tool_name}

    [결과]
    {tool_result}

    [사용자 정보]
    {json.dumps(context, ensure_ascii=False)}

    이 결과가 요청에 비춰볼 때 충분하고 유효한지 판단해줘.
    부족하면 재시도 이유와 제안도 포함해줘.

    출력 예시:
    {{
      "valid": true,
      "reason": "결과가 적절함",
      "suggestion": "",
      "next_action": "final_response"
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()

@tool
def search_food_tool(params: dict) -> str:
    """
    음식명을 기반으로 자동완성 및 오타 허용 검색을 수행하고,
    가장 유사한 음식의 영양정보를 반환합니다.
    """

    # ✅ ES 검색 (자동완성 + 오타 통합)
    es_query = {
        "query": {
            "bool": {
                "should": [
                    {"match": {"name": {"query": params, "fuzziness": "AUTO"}}},
                    {"match_phrase_prefix": {"name": {"query": params}}}
                ]
            }
        }
    }

    results = es.search(index="food_nutrition_index", body=es_query)
    hits = results["hits"]["hits"]
    if not hits:
        return f"'{params}'에 대한 음식 검색 결과가 없습니다."

    top_hit = hits[0]["_source"]
    food_id = top_hit["id"]
    name = top_hit["name"]

    # ✅ PostgreSQL에서 영양정보 조회
    pg_cur.execute("SELECT * FROM food_nutrition WHERE id = %s", (food_id,))
    row = pg_cur.fetchone()
    if not row:
        return f"{name}의 영양 정보를 찾을 수 없습니다."

    result = f"🍽️ 추천 음식: {name}\n📊 영양정보:\n"
    columns = [desc[0] for desc in pg_cur.description]
    for col, val in zip(columns, row):
        result += f"- {col}: {val}\n"
    return result
def extract_json_block(text: str) -> str:
    import re
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

def check_duplicate_meal_via_sql(member_id: int, food_name: str, meal_type: str) -> bool:
    query = f"""
    SELECT COUNT(*) AS count
    FROM meal_records
    WHERE member_id = {member_id}
      AND food_name = '{food_name}'
      AND meal_type = '{meal_type}'
      AND meal_date = CURRENT_DATE
    """
    result_json = execute_sql(query)
    result = json.loads(result_json)
    
    # SQL 실행 오류인 경우
    if isinstance(result, dict) and "error" in result:
        print("❌ SQL 오류 발생:", result["error"])
        return False

    return result[0]["count"] > 0

@tool
def get_meal_records_tool(params: dict) -> str:
    """
    사용자의 최근 식사 기록을 조회합니다.
    - params 예시: { "member_id": 3, "days": 7 }
    - 날짜 기준 최근 N일간의 meal_records 조회
    """
    try:
        member_id = params.get("member_id")
        days = int(params.get("days", 7))

        if not member_id:
            return "❌ member_id가 제공되지 않았습니다."

        interval = f"{days} days"
        query = f"""
        SELECT * FROM meal_records
        WHERE member_id = {member_id}
        AND meal_date >= CURRENT_DATE - INTERVAL '{interval}'
        AND is_deleted = false
        ORDER BY meal_date DESC;
        """

        # ⛳ raw JSON string 반환
        raw_result = execute_sql(query)

        # ✅ datetime 대응을 위해 dict로 로드한 뒤 재직렬화
        try:
            data = json.loads(raw_result)

            def serialize(obj):
                import datetime
                if isinstance(obj, (datetime.datetime, datetime.date)):
                    return obj.isoformat()
                if isinstance(obj, datetime.time):  # ✅ 여기를 꼭 추가!
                    return obj.strftime("%H:%M:%S")
                raise TypeError(f"Type {type(obj)} not serializable")

            return json.dumps(data, default=serialize, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"❌ JSON 파싱 실패: {e}\n\n[원본 응답]\n{raw_result}"

    except Exception as e:
        return f"❌ 식사 기록 조회 실패: {e}"

@tool
def record_meal_tool(params: dict) -> str:
    """
    자연어 식사 입력 → 음식명/양/단위 파싱 → 영양정보 조회 → Spring Boot API로 meal_records 저장 또는 갱신
    """
    try:
        print(f"✅ 입력 파라미터: {params}")
        user_input = params.get("user_input") or params.get("input", "")
        member_id = params.get("member_id", 1)

        # 🥣 식사 정보 파싱
        parsed = meal_parser_tool.invoke({"params": {"user_input": user_input}})
        parsed_json = json.loads(extract_json_block(parsed))
        print(f"✅ 파싱 결과: {parsed_json}")

        food_name = parsed_json.get("food_name")
        meal_type = parsed_json.get("meal_type")
        portion = parsed_json.get("portion", 100) or 100
        unit = parsed_json.get("unit", "g") or "g"

        # 🧪 영양 정보 조회
        nutrition_json = lookup_nutrition_tool.invoke({"params": {"user_input": food_name}})
        nutrition_data = json.loads(extract_json_block(nutrition_json))
        print(f"✅ 영양정보: {nutrition_data}")

        factor = portion / 100
        calories = round(nutrition_data["calories"] * factor, 1)
        protein = round(nutrition_data["protein"] * factor, 1)
        carbs = round(nutrition_data["carbs"] * factor, 1)
        fat = round(nutrition_data["fat"] * factor, 1)

 
        is_duplicate = check_duplicate_meal_via_sql(member_id, food_name, meal_type)

        if is_duplicate:
            print("♻️ 중복 → 업데이트")
        else:
            print("✅ 신규 → 인서트")

        # 🌱 insert/update에 사용할 전체 데이터
        meal_data = {
               "memberId": member_id,
                "foodName": food_name,
                "mealType": meal_type,
                "portion": portion,
                "unit": unit,
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat
        }

        print(f"🔍 식사 데이터: {meal_data}")
        if is_duplicate:  # 기존 식사 기록 있음 → update
            api_result = call_spring_api("/api/food/update-meal", meal_data, "PUT")
            status = "♻️ 기존 기록 갱신 완료"
        else:  # 없으면 insert
            api_result = call_spring_api("/api/food/insert-meal", meal_data, "POST")
            status = "✅ 새 식사 기록 저장 완료"

        if "error" in api_result:
            raise Exception(api_result["error"])

        return json.dumps({
            "status": status,
            "food": food_name,
            "meal_type": meal_type,
            "portion": portion,
            "unit": unit,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ 저장 실패: {str(e)}\n{traceback.format_exc()}"


tool_list = [
    record_meal_tool,
    search_food_tool ,
    general_result_validator,
    caloric_target_tool,
    nutrition_gap_feedback_tool,
    meal_record_gap_report_tool,
    auto_tdee_wrapper,
    tdee_calculator_tool,
    nutrition_goal_gap_tool,
    diet_explanation_tool,
    save_recommended_diet,
    recommend_food_tool,
    recommend_diet_tool,
    sql_query_runner,
    sql_insert_runner,
    ask_missing_slots,
    lookup_nutrition_tool,
    validate_result_tool,
    diet_feedback_tool,
    summarize_nutrition_tool,
    weekly_average_tool,
    user_profile_tool,
    meal_parser_tool,
    save_user_goal_and_diet_info,
get_meal_records_tool,
    
]
 