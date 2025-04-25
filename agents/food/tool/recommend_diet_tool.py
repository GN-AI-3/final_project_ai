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


from cgitb import text
from datetime import datetime
import json
import re
from typing import Dict
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from langchain_community.retrievers import TavilySearchAPIRetriever
from agents.food.util.table_schema import table_schema
from agents.food.llm_config import llm
import psycopg2
import traceback
from elasticsearch import Elasticsearch
import requests
import os
from pathlib import Path
from ..config.api_config import EC2_BACKEND_URL, AUTH_TOKEN
from ..config.database_config import PG_URI

# agents/food 디렉토리 경로 찾기
agents_food_dir = Path(__file__).parent.parent

# 환경 변수 로드
load_dotenv()

def call_spring_api(endpoint: str, data: dict, method: str = "POST") -> dict:
    """
    스프링 부트 API를 호출하는 함수
    - method: "POST" 
    - JWT 토큰은 환경 변수에서 로드
    """
    url = f"{EC2_BACKEND_URL}{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    method = method.upper()

    try:
        if method == "PUT": 
            response = requests.put(url, json=data, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            return {"error": f"지원하지 않는 HTTP 메서드: {method}"}
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"API 호출 실패: {str(e)}"}

# Elasticsearch 연결
es = Elasticsearch(os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"))

# PostgreSQL 연결
def get_db_connection():
    try:
        return psycopg2.connect(PG_URI)
    except Exception as e:
        print(f"데이터베이스 연결 오류: {str(e)}")
        return None

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor() if pg_conn else None

# 실제 DB 실행 유틸 (psycopg2 기반)
def execute_sql(query: str) -> str:
    def serialize(obj):
        import datetime
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, datetime.time):
            return obj.strftime("%H:%M:%S")
        raise TypeError(f"Type {type(obj)} not serializable")
    
    global pg_conn, pg_cur
    
    try:
        # 연결이 끊어졌거나 없는 경우 재연결
        if not pg_conn or pg_conn.closed:
            pg_conn = get_db_connection()
            if not pg_conn:
                return json.dumps({"status": "❌ 데이터베이스 연결 실패"}, ensure_ascii=False)
            pg_cur = pg_conn.cursor()
        
        pg_cur.execute(query)

        if query.strip().lower().startswith("select"):
            rows = pg_cur.fetchall()
            columns = [desc[0] for desc in pg_cur.description]
            data = [dict(zip(columns, row)) for row in rows]
            result = json.dumps(data, default=serialize, ensure_ascii=False, indent=2)
        else:
            pg_conn.commit()
            result = json.dumps({"status": "✅ SQL 실행 완료"}, ensure_ascii=False)

        return result

    except Exception as e:
        import traceback
        # 에러 발생 시 연결 초기화
        if pg_cur:
            try:
                pg_cur.close()
            except:
                pass
        if pg_conn:
            try:
                pg_conn.close()
            except:
                pass
        pg_cur = None
        pg_conn = None
        
        return json.dumps({
            "status": "❌ SQL 실행 오류",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, ensure_ascii=False)



@tool
def web_search_and_summary(params: dict) -> str:
    """모르는건 웹 검색을 수행합니다."""
    query = params.get("user_input", "")
    retriever = TavilySearchAPIRetriever(k=3, tavily_api_key=os.getenv("TAVILY_API_KEY"))

    docs = retriever.invoke(query)

    prompt = PromptTemplate.from_template("""
    다음은 웹에서 검색한 결과입니다.
    질문: {query}
    문서: {docs}

    이 정보를 요약해줘.
    """)
    prompt_text = prompt.format(query=query, docs=docs)
    return llm.invoke([HumanMessage(content=prompt_text)]).content.strip()

def clean_sql(sql: str) -> str:
    import re
    return re.sub(r"```(?:sql)?", "", sql).replace("```", "").strip()


@tool
def sql_query_runner(params: dict) -> str:
    """
    사용자의 자연어 입력을 기반으로 SQL SELECT 쿼리를 생성하고 실행합니다.
    """

    user_input = params.get("input", "")
    member_id = params.get("member_id")

    if not user_input or not member_id:
        return "❌ 'input'과 'member_id'는 필수입니다."

    try:
        # ✅ SQL 생성
        raw_sql = generate_sql(user_input, member_id=member_id)

        # ✅ 마크다운 제거
        cleaned_sql = clean_sql(raw_sql)

        # ✅ SQL 실행
        result = execute_sql(cleaned_sql)

        return f"✅ [SQL 실행 결과]\n\n🧾 SQL: {cleaned_sql}\n📦 결과:\n{result}"

    except Exception as e:
        return f"❌ SQL 실행 중 오류 발생: {e}"

@tool
def sql_insert_runner(params: str, member_id: int) -> str:
    """사용자의 요청을 기반으로 SQL INSERT 쿼리를 생성하고 실행합니다."""
    sql = generate_sql(params + " (insert 쿼리 형식으로)", member_id=member_id)
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
    기존 값과 병합하며, 제거 요청이 있는 경우 해당 값을 제거합니다.
    """

    def extract_json_string(text: str) -> str:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        if text.strip().startswith("{"):
            return text.strip()
        return ""

    def merge_values(existing: str, new_value: str, remove: bool = False) -> str:
        existing = existing or ""  # None 방지
        new_value = new_value or ""
        existing_set = set([x.strip() for x in existing.split(",") if x.strip()])
        new_set = set([x.strip() for x in new_value.split(",") if x.strip()])
        if remove:
            result_set = existing_set - new_set
        else:
            result_set = existing_set | new_set
        return ",".join(sorted(result_set))

    try:
        user_input = params.get("input", "")
        member_id = params.get("member_id", 1)

        # 기존 식단 정보 조회
        select_sql = f"SELECT * FROM member_diet_info WHERE member_id = {member_id}"
        existing_result = execute_sql(select_sql)
        existing_data = json.loads(existing_result)[0] if existing_result else {}

        # LLM 추출 프롬프트
        extract_prompt = f"""
        다음은 사용자의 자연어 입력이야. 사용자의 의도에 따라 기존 값에 대한 '추가(add)' 또는 '제거(remove)' 정보를 판단해줘.
        각 항목은 문자열로, 누락된 값은 빈 문자열로 반환해.

        ✅ 판단 기준:
        - "좋아해", "선호해", "먹고 싶어", "더 넣어줘", "추가해줘" 등은 → food_preferences로 add
        - "싫어해", "안 좋아해", "피하고 싶어", "비선호", "꺼려", "먹기 싫어" 등은 → food_avoidances로 add
        - "알레르기 있어", "과민반응 있어"는 → allergies로 add
        - "빼줘", "제외해줘", "이제 안 먹어", "삭제해줘" 등은 → remove로 처리 (context 보고 분기 가능)

        💡 문맥이 모호한 경우, 아래처럼 판단해줘:
        - "조류는 싫어해요" → food_avoidances (add)
        - "견과류 알레르기 있어요" → allergies (add)
        - "두부는 빼줘" → food_avoidances (add)

        [입력]
        {user_input}

        [출력 예시]
        {{
        "goal": "다이어트",
        "gender": "남성",
        "add": {{
            "allergies": "견과류",
            "food_preferences": "소고기",
            "food_avoidances": "두부"
        }},
        "remove": {{
            "food_avoidances": "밀가루",
              "food_preferences": "고기",
  "allergies": "두부"
        }}
        }}
        """


        response = llm.invoke([HumanMessage(content=extract_prompt)])
        raw_response = response.content.strip()
        print(raw_response)
        if not raw_response:
            return "❌ LLM 응답이 비어 있습니다."

        json_str = extract_json_string(raw_response)
        parsed = json.loads(json_str)

        # 사용자 정보 업데이트
        if parsed.get("goal") or parsed.get("gender"):
            member_data = {
                "memberId": member_id,
                "goal": parsed.get("goal", existing_data.get("goal", "")),
                "gender": parsed.get("gender", existing_data.get("gender", ""))
            }
            member_result = call_spring_api("/api/member/update", member_data, method="POST")
            if "error" in member_result:
                return f"❌ 사용자 정보 업데이트 실패: {member_result['error']}"

        # 병합 처리
        add = parsed.get("add", {})
        remove = parsed.get("remove", {})

        diet_info_data = {
            "memberId": member_id,
            "allergies": merge_values(existing_data.get("allergies"), add.get("allergies")) if add.get("allergies") else merge_values(existing_data.get("allergies"), remove.get("allergies"), remove=True) if remove.get("allergies") else existing_data.get("allergies", ""),
            "foodPreferences": merge_values(existing_data.get("food_preferences"), add.get("food_preferences")) if add.get("food_preferences") else merge_values(existing_data.get("food_preferences"), remove.get("food_preferences"), remove=True) if remove.get("food_preferences") else existing_data.get("food_preferences", ""),
            "mealPattern": parsed.get("meal_pattern", existing_data.get("meal_pattern", "") or ""),
            "activityLevel": parsed.get("activity_level", existing_data.get("activity_level", "") or ""),
            "specialRequirements": parsed.get("special_requirements", existing_data.get("special_requirements", "") or ""),
            "foodAvoidances": merge_values(existing_data.get("food_avoidances"), add.get("food_avoidances")) if add.get("food_avoidances") else merge_values(existing_data.get("food_avoidances"), remove.get("food_avoidances"), remove=True) if remove.get("food_avoidances") else existing_data.get("food_avoidances", "")
        }
        print(diet_info_data)
        # 저장 API 호출
        method = "PUT" if existing_data else "POST"
        result = call_spring_api("/api/food/user/diet-info", diet_info_data, method=method)

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
    - Step 2: Elasticsearch 결과를 기반으로 LLM으로 일치 여부 판단
    - Step 3: 일치하지 않으면 Tavily + LLM 추론 (DB/ES 저장은 ❌)
    - Step 4: Tavily에서도 없으면 LLM 추론
    """

    food_name = params.get("food_name") or params.get("user_input") or params.get("input", "").strip()

    if not food_name:
        return "❌ 음식 이름이 제공되지 않았습니다."

    try:
        # Step 1: Elasticsearch 검색 (자동완성 + 오타 허용)
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
            # Step 2: Elasticsearch에서 반환된 음식명 확인
            food_id = hits[0]["_source"]["id"]
            matched_food_name = hits[0]["_source"]["name"]
            
            # LLM으로 음식 이름이 일치하는지 판단
            prompt = PromptTemplate.from_template("""\
                사용자가 입력한 음식 이름은 '{food_name}'입니다.
                Elasticsearch에서 반환된 음식 이름은 '{matched_food_name}'입니다.
                이 두 음식 이름이 동일한지 확인하고, 그 이유를 설명해주세요.
                예시:
                - '맞습니다' 또는 '다릅니다'
            """)
            
            formatted_prompt = prompt.format(food_name=food_name, matched_food_name=matched_food_name)
            response = llm.invoke([HumanMessage(content=formatted_prompt)])
            
            # 일치한다고 판단되면 PostgreSQL에서 영양 정보 조회
            if "맞습니다" in response.content:
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

        # Step 3: Elasticsearch 결과가 없거나 일치하지 않으면 Tavily + LLM 추론
        retriever = TavilySearchAPIRetriever(k=3, tavily_api_key=os.getenv("TAVILY_API_KEY"))
        info = retriever.invoke(f"{food_name} 100g 칼로리 단백질 지방 탄수화물")

        if not info:
            # Step 4: Tavily에서 정보가 없으면 LLM을 통한 추론
            prompt = f"""
            사용자가 요청한 음식 '{food_name}'에 대한 영양 성분을 100g 기준으로 추론해줘.
            - 칼로리, 단백질, 지방, 탄수화물 수치를 예측해서 JSON 형식으로 출력해줘.
            예시:
            {{
              "food_item_name": "{food_name}",
              "calories": ...,
              "protein": ...,
              "fat": ...,
              "carbs": ...
            }}
            """
            response = llm.invoke([HumanMessage(content=prompt)])
            return f"🧠 [LLM 추론 결과]\n{response.content.strip()}"

        # Tavily에서 영양 정보가 있으면 출력
        prompt = PromptTemplate.from_template("""\
            아래 문서에서 "{food_name} 100g" 기준으로
            칼로리, 단백질, 지방, 탄수화물 수치를 JSON으로 정리해줘.
            없으면 너가 추론해서 적어줘.
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
        return f"🧠 [LLM 추론 결과]\n{response.content.strip()}"

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
- 질문이 "무엇인가요?", "알려줘", "보여줘" 등으로 끝나면 → SELECT
- "저장해", "입력해", "수정해" → INSERT or UPDATE
-- 다음 조건을 반드시 지켜라:
- 반드시 SQL만 출력하고 설명은 금지한다.
- SELECT/INSERT/UPDATE 등 적절한 쿼리를 생성해라.
- 테이블 이름과 컬럼명을 반드시 일치시켜라.
- 모든 쿼리는 특정 사용자의 데이터를 조회해야 하며, WHERE 절에 반드시 "member_id = {member_id}" 조건이 있어야 한다.

[출력 형식 예시]
SELECT * FROM ... WHERE ...;
""")



def generate_sql(user_input: str, member_id: int) -> str:
    prompt = SQL_PROMPT.format(schema_text=table_schema, user_input=user_input, member_id=member_id)
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
    사용자 ID에 기반해 개인 맞춤 식단을 추천하고,
    TDEE 기반 영양 목표, 요약, 피드백 및 DB 저장까지 수행합니다.
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
        """
        텍스트에서 JSON 블록을 추출하는 함수.
        """
        try:
            # JSON 구문 오류가 있을 경우 처리할 수 있는 코드 추가
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()  # JSON 문자열 추출
            if text.strip().startswith("{"):
                return text.strip()  # 시작이 '{'이면 바로 반환
            return ""  # JSON 형식이 아니면 빈 문자열 반환
        except Exception as e:
            return ""  # 예외가 발생하면 빈 문자열 반환



    try:
        member_id = int(params.get("member_id", 1))
        raw_period = params.get("period") or params.get("meal_type") or "하루"
        period = standardize_period(raw_period)

        context = params.get("context", {})
        member_info = context.get("member", {})
        diet_info = context.get("user_diet_info", {})

        goal_raw = normalize(member_info.get("goal"), "체중 감량")
        gender = normalize(member_info.get("gender"), "남성")
        special = normalize(diet_info.get("special_requirements"))
        allergies = normalize(diet_info.get("allergies"))
        preferences = normalize(diet_info.get("food_preferences"))
        pattern = normalize(diet_info.get("meal_pattern"))
        avoidances = normalize(diet_info.get("food_avoidances"))

        # ✅ goal 분류 (6개 중 하나)
        goal_prompt = f"""
        다음 목표를 아래 식단 유형 중 하나로 분류해줘:
        - 다이어트 식단
        - 벌크업 식단
        - 체력 증진 식단
        - 유지/균형 식단
        - 고단백/저탄수화물 식단
        - 고탄수/고단백 식단
        목표: {goal_raw}
        """
        goal_response = llm.invoke([HumanMessage(content=goal_prompt)]).content.strip()
        goal = goal_response if goal_response in [
            "다이어트 식단", "벌크업 식단", "체력 증진 식단",
            "유지/균형 식단", "고단백/저탄수화물 식단", "고탄수/고단백 식단"
        ] else "유지/균형 식단"

        # 🎯 매크로 비율 정의
        goal_macro_ratios = {
            "다이어트 식단": {"protein_ratio": 0.30, "carbs_ratio": 0.45, "fat_ratio": 0.25, "examples": "닭가슴살, 브로콜리, 현미밥"},
            "벌크업 식단": {"protein_ratio": 0.30, "carbs_ratio": 0.55, "fat_ratio": 0.15, "examples": "소고기, 고구마, 귀리, 올리브유"},
            "체력 증진 식단": {"protein_ratio": 0.25, "carbs_ratio": 0.55, "fat_ratio": 0.20, "examples": "연어, 통밀 파스타, 바나나"},
            "유지/균형 식단": {"protein_ratio": 0.25, "carbs_ratio": 0.50, "fat_ratio": 0.25, "examples": "두부, 잡곡밥, 달걀, 시금치"},
            "고단백/저탄수화물 식단": {"protein_ratio": 0.40, "carbs_ratio": 0.35, "fat_ratio": 0.25, "examples": "닭가슴살, 아보카도, 삶은 달걀"},
            "고탄수/고단백 식단": {"protein_ratio": 0.30, "carbs_ratio": 0.55, "fat_ratio": 0.15, "examples": "현미밥, 흰살생선, 고구마, 콩류"},
        }

        macro_ratio = goal_macro_ratios.get(goal, goal_macro_ratios["유지/균형 식단"])

        protein_ratio = macro_ratio['protein_ratio']
        carbs_ratio = macro_ratio['carbs_ratio']
        fat_ratio = macro_ratio['fat_ratio']
        example_foods = macro_ratio['examples']

        height = float(member_info.get("height", 170))
        weight = float(member_info.get("weight", 70))
        birth_date = member_info.get("birth_date", "2000-01-01")
        birth = datetime.strptime(birth_date, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "남성" else -161)
        tdee = bmr * 1.2

        if "감량" in goal or "다이어트 식단" in goal:
            target_calories = tdee - 500
        elif "증가" in goal or "벌크업 식단" in goal:
            target_calories = tdee + 500
        else:
            target_calories = tdee

        nutrition_goals = {
            "target_calories": round(target_calories),
            "protein": round((target_calories * protein_ratio) / 4),
            "carbs": round((target_calories * carbs_ratio) / 4),
            "fat": round((target_calories * fat_ratio) / 9),
        }
        if period == "한끼":
            meal_type = params.get("meal_type", "점심")  # 기본값: 점심

            example_sql = f"""
            SELECT breakfast, lunch, dinner
            FROM diet_plans
            WHERE diet_type = '{goal}'
            AND user_gender = '{gender}'
            LIMIT 1;
            """
            raw_examples_str = execute_sql(example_sql)

            try:
                raw_examples = json.loads(raw_examples_str)
            except json.JSONDecodeError as e:
                return json.dumps({
                    "status": "❌ 식단 예시 로딩 실패",
                    "error": f"JSON 디코딩 오류: {str(e)}",
                    "raw_result": raw_examples_str
                }, ensure_ascii=False)

            meal_key_map = {
                "아침": "breakfast",
                "점심": "lunch",
                "저녁": "dinner"
            }
            selected_key = meal_key_map.get(meal_type, "lunch")

            one_meal_examples = []
            for row in raw_examples:
                if isinstance(row, dict):
                    value = row.get(selected_key)
                    if value:
                        one_meal_examples.append({"meal": value})

            example_data = json.dumps(one_meal_examples, ensure_ascii=False, indent=2)
            plan_format = '"meal": "..."'

        else:
            
            example_sql = f"""
            SELECT breakfast, lunch, dinner
            FROM diet_plans
            WHERE diet_type = '{goal}'
            AND user_gender = '{gender}'
            LIMIT 1;
            """
            example_data = execute_sql(example_sql)

        if period == "하루":
            plan_format = '"monday": {"아침": "...", "점심": "...", "저녁": "..."}'
        elif period == "일주일":
            plan_format = '"monday": {"아침": "...", "점심": "...", "저녁": "..."}, "tuesday": {...}, ...'
        elif period == "한끼":
            plan_format = '"meal": "..."'
        else:
            plan_format = '"monday": {"아침": "...", "점심": "...", "저녁": "..."}'

        prompt = f"""
        한국 사용자에게 맞춤 식단을 {period} 기준으로 추천해줘.

        [사용자 정보]
        - 목표: {goal_raw}
        - 성별: {gender}
        - 기타 사항: {special}
        - 알레르기: {allergies}
        - 음식 기호: {preferences}
        - 식사 패턴: {pattern}
        - 거부 음식: {avoidances}
        - 목표 영양소: {nutrition_goals}
        - 주요 식품 예시: {example_foods}
        [목표 식단의 식품군 기준]
        - 단백질원: 육류(닭, 소), 생선, 두부, 달걀, 유제품 등
        - 탄수화물원: 통곡물(현미, 귀리), 감자, 고구마, 과일 등
        - 지방원: 견과류, 올리브유, 아보카도 등
        - 채소류: 브로콜리, 시금치, 양배추 등

        [식단 예시] (단, 단순 참고용입니다)
        {example_data}
        요청 조건]
        - 제공된 식단 예시는 단순 참고용이며, 반드시 같은 구성일 필요는 없습니다.
        - 매번 **새로운 재료 조합**과 **창의적인 변형**을 고려해 구성해주세요.
        - 단백질, 탄수화물, 지방, 채소류의 균형은 유지하면서 **다양성을 극대화** 해주세요.
        - 식사는 가능한 한 **다양한 재료**를 사용해 반복을 줄여주세요.
        - 예시 식품 목록 외에도 비슷한 영양 특성을 가진 식품으로 **대체 식품**도 활용해도 됩니다.
        - 식사 시간대별 소화 부담도 반영해주세요 (예: 저녁은 가볍게).
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

        raw_json = extract_json_block(plan_result)
        plan_json = json.loads(raw_json)
        json_text = extract_json_block(plan_result)

        if not plan_json.get("summary") or "0 kcal" in json.dumps(plan_json["summary"]):
            summary = summarize_nutrition_tool.invoke({"params": {"user_input": json_text}})
            plan_json["summary"] = json.loads(summary)

        feedback = diet_feedback_tool.invoke({
            "params": {
                "input": json_text,
                "member_id": member_id,
                "goal": goal
            }
        })
        plan_json["feedback"] = json.loads(feedback)
        plan_json["nutrition_goals"] = nutrition_goals
        if period == "한끼":
            meal_type = params.get("meal_type", "점심")
            current_plan = plan_json.get("plan", {})

            # 이미 변환된 구조인지 확인
            if "single" not in current_plan:
                meal_data = current_plan.get("meal", "")
                plan_json["plan"] = {
                    "single": {
                        meal_type: meal_data
                    }
                }

        save_result = save_recommended_diet.invoke({
            "params": {
                "user_input": json.dumps(plan_json, ensure_ascii=False),
                "member_id": member_id
            }
        })
        plan_json["save_result"] = save_result

        return json.dumps(plan_json, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "❌ 식단 추천 오류",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, ensure_ascii=False)

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
def infer_meal_type_from_time():
    now = datetime.now().hour
    if 5 <= now < 11:
        return "아침"
    elif 11 <= now < 16:
        return "점심"
    elif 16 <= now < 21:
        return "저녁"
    return None  # 새벽이나 야식

@tool
def meal_parser_tool(params: dict) -> str:
    """
    자연어 식사 기록에서 음식명(복수), 양, 단위, 식사 시간/끼니, 그리고 g 기준 추정량까지 추출합니다.
    """
    from datetime import datetime
    user_input = params.get("user_input", "")
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_meal_type = infer_meal_type_from_time()

    prompt = f"""
    너는 식사 기록 분석기야.

    입력된 문장에서 다음 항목을 추출해서 정확한 JSON 형태로 출력해줘.
    만약 문장에 식사명이 직접 포함되지 않았다면, 시간 "{now_time}" 기준으로 다음을 적용해서 끼니를 정해줘:

    - 05:00~10:59 → 아침
    - 11:00~15:59 → 점심
    - 16:00~21:00 → 저녁
    - 그 외 시간은 기타

    ⚠️ JSON만 출력하고, 설명 없이 순수 JSON 객체만 포함해야 해.
    
    입력 문장: "{user_input}"

    추출 항목:
    - meal_type: 아침 / 점심 / 저녁 중 하나 (또는 null)
    - food_name: ["음식1", "음식2", ...]
    - portion: [정수 또는 실수]
    - unit: ["개", "공기", "g", ...]
    - estimated_grams: [g 단위 추정량]

    출력 예시:
    {{
      "meal_type": "{default_meal_type}",
      "food_name": ["닭가슴살", "현미밥"],
      "portion": [1, 1],
      "unit": ["개", "공기"],
      "estimated_grams": [150, 200]
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()

@tool
def save_recommended_diet(params: dict) -> str:
    """
    추천된 식단(JSON)을 recommended_diet_plans 테이블에 저장
    """
    try:
        user_input = params.get("user_input", "{}")
        if isinstance(user_input, dict):
            plan = user_input
        else:
            plan = json.loads(user_input)

        member_id = params.get("member_id", 1)
        scope = plan.get("scope", "하루")
        comment = plan.get("comment", "")
        raw_plan = plan.get("plan", {})

        plan_json = {}

        if scope == "한끼":
            meal_plan = raw_plan.get("meal", {})
            # 한끼니까 실제로 한 끼만 보내야 함
            for meal_key in ["breakfast", "lunch", "dinner", "아침", "점심", "저녁"]:
                if meal_key in meal_plan:
                    # 예: "single": { "아침": "...한끼..." }
                    plan_json = {"single": {meal_key: meal_plan[meal_key]}}
                    break  # 하나만 보내야 하므로 break
                            
        elif scope == "하루":
            if "monday" in raw_plan:
                plan_json = raw_plan
            else:
                plan_json = {
                    "monday": {
                        "아침": raw_plan.get("breakfast", "") or raw_plan.get("아침", ""),
                        "점심": raw_plan.get("lunch", "") or raw_plan.get("점심", ""),
                        "저녁": raw_plan.get("dinner", "") or raw_plan.get("저녁", "")
                    }
                }

        elif scope == "일주일":
            # 일주일 → 이미 요일별로 구성된 dict 그대로 사용
            plan_json = raw_plan

        else:
            return f"❌ 지원하지 않는 scope: {scope}"

        save_result = call_spring_api(
            endpoint="/api/food/recommended-diet-plan",
            data={
                "memberId": member_id,
                "planScope": scope,
                "planSummary": comment,
                "planJson": plan_json
            }
        )
        return f"\n{json.dumps(plan_json, ensure_ascii=False, indent=2)}"

    except Exception as e:
        return f"❌ 저장 실패: {str(e)}"


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
    if not text.strip():
        return ""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if text.strip().startswith("{") and text.strip().endswith("}"):
        return text.strip()
    return ""

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
def get_weight_from_inbody(member_id: int) -> float:
    """가장 최근 인바디 기록에서 체중을 가져옵니다."""
    result = execute_sql(f"""
        SELECT weight FROM inbody
        WHERE member_id = {member_id}
        ORDER BY date DESC
        LIMIT 1
    """)
    return float(json.loads(result)[0]["weight"]) if result else 0.0


def get_user_goal(member_id: int) -> str:
    """사용자의 최근 goal 필드를 기반으로 LLM이 식단 유형으로 분류합니다."""
    result = execute_sql(f"""
        SELECT goal FROM member
        WHERE id = {member_id}
    """)

    if not result:
        return "유지/균형 식단"

    goal_raw = json.loads(result)[0]["goal"]

    # ✅ goal LLM 분류 요청
    goal_prompt = f"""
    다음 목표를 아래 식단 유형 중 하나로 분류해줘:
    - 다이어트 식단
    - 벌크업 식단
    - 체력 증진 식단
    - 유지/균형 식단
    - 고단백/저탄수화물 식단
    - 고탄수/고단백 식단
    목표: {goal_raw}
    """
    goal_response = llm.invoke([HumanMessage(content=goal_prompt)]).content.strip()

    # ✅ 허용된 식단 유형만 통과
    valid_goals = [
        "다이어트 식단", "벌크업 식단", "체력 증진 식단",
        "유지/균형 식단", "고단백/저탄수화물 식단", "고탄수/고단백 식단"
    ]
    return goal_response if goal_response in valid_goals else "유지/균형 식단"


def auto_nutrition_goal(member_id: int) -> Dict:
    """
    사용자 목표와 체중 기반으로 TDEE 및 하루 영양소 목표를 계산합니다.
    탄단지 비율은 목표에 따라 자동 적용됩니다.
    """
    weight = get_weight_from_inbody(member_id)
    goal = get_user_goal(member_id)

    # ✅ 목표별 탄단지 비율 설정
    ratios = {
        "다이어트 식단": (0.35, 0.4, 0.25),
        "벌크업 식단": (0.3, 0.5, 0.2),
        "체력 증진 식단": (0.3, 0.45, 0.25),
        "유지/균형 식단": (0.3, 0.4, 0.3),
        "고단백/저탄수화물 식단": (0.45, 0.25, 0.3),
        "고탄수/고단백 식단": (0.35, 0.5, 0.15)
    }

    # 기본 비율: 유지
    protein_r, carb_r, fat_r = ratios.get(goal, ratios["유지/균형 식단"])

    # ✅ TDEE 계산 (체중 * 33 kcal 기준)
    tdee = round(weight * 33)

    return {
        "goal": goal,
        "calories": tdee,
        "protein": round(tdee * protein_r / 4),  # 단백질 1g = 4kcal
        "carbs": round(tdee * carb_r / 4),       # 탄수화물 1g = 4kcal
        "fat": round(tdee * fat_r / 9)           # 지방 1g = 9kcal
    }
def make_llm_feedback_prompt(nutrition_target, nutrition_summary, nutrition_remaining):
    def percent(part, total):
        return round(part / total * 100) if total else 0

    percent_summary = {
        "calories": percent(nutrition_summary["총칼로리"], nutrition_target["calories"]),
        "protein": percent(nutrition_summary["단백질"], nutrition_target["protein"]),
        "carbs": percent(nutrition_summary["탄수화물"], nutrition_target["carbs"]),
        "fat": percent(nutrition_summary["지방"], nutrition_target["fat"]),
    }

    # ✅ LLM 프롬프트
    return f"""
당신은 영양 분석 전문가입니다.

오늘 사용자의 하루 영양 목표는 다음과 같습니다:
- 칼로리: {nutrition_target['calories']} kcal
- 단백질: {nutrition_target['protein']} g
- 탄수화물: {nutrition_target['carbs']} g
- 지방: {nutrition_target['fat']} g

현재까지 사용자가 섭취한 양은 다음과 같습니다:
- 칼로리: {nutrition_summary['총칼로리']} kcal ({percent_summary['calories']}%)
- 단백질: {nutrition_summary['단백질']} g ({percent_summary['protein']}%)
- 탄수화물: {nutrition_summary['탄수화물']} g ({percent_summary['carbs']}%)
- 지방: {nutrition_summary['지방']} g ({percent_summary['fat']}%)

남은 목표 섭취량:
- 칼로리: {nutrition_remaining['calories']} kcal
- 단백질: {nutrition_remaining['protein']} g
- 탄수화물: {nutrition_remaining['carbs']} g
- 지방: {nutrition_remaining['fat']} g

이 데이터를 기반으로 다음 사항을 포함한 친절하고 간결한 피드백 문장을 작성해주세요:
- 어떤 영양소가 부족하거나 초과되었는지
- 다음 식사에서 어떤 식품군을 보충하면 좋을지
- 과잉 섭취 시 주의해야 할 점
"""

@tool
def record_meal_tool(params: dict) -> str:
    """
    자연어 식사 입력 → 식사 파싱 및 DB 저장 → 한 끼 요약 + 하루 누적 + LLM 기반 피드백 반환
    """
    try:
        import traceback
        from datetime import datetime

        inner = params.get("params", params)
        user_input = inner.get("input") or inner.get("user_input", "")
        member_id = inner.get("member_id", 1)

        parsed = meal_parser_tool.invoke({"params": {"user_input": user_input}})
        json_block = extract_json_block(parsed)
        if not json_block:
            return f"❌ LLM 식사 파싱 실패\n파일: {parsed}"
        parsed_json = json.loads(json_block)

        meal_type = parsed_json.get("meal_type")
        food_names = parsed_json.get("food_name", [])
        portions = parsed_json.get("portion", [])
        units = parsed_json.get("unit", [])
        estimated_grams = parsed_json.get("estimated_grams", [])

        results = []
        total_calories = total_protein = total_carbs = total_fat = 0

        for i, food in enumerate(food_names):
            portion = portions[i] if i < len(portions) else 1
            unit = units[i] if i < len(units) else "g"
            grams = estimated_grams[i] if i < len(estimated_grams) else 100

            nutrition_json = lookup_nutrition_tool.invoke({"params": {"user_input": food}})
            try:
                nutrition_data = json.loads(extract_json_block(nutrition_json))
            except:
                nutrition_data = {}

            if not nutrition_data:
                results.append({"status": "❌ 영양 정보 없음", "food": food})
                continue

            factor = grams / 100
            calories = round(nutrition_data.get("calories", 0) * factor, 1)
            protein = round(nutrition_data.get("protein", 0) * factor, 1)
            carbs = round(nutrition_data.get("carbs", 0) * factor, 1)
            fat = round(nutrition_data.get("fat", 0) * factor, 1)

            total_calories += calories
            total_protein += protein
            total_carbs += carbs
            total_fat += fat

            meal_data = {
                "memberId": member_id,
                "foodName": food,
                "mealType": meal_type,
                "portion": float(portion),
                "unit": unit,
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
                "estimated_grams": grams
            }

            api_result = call_spring_api("/api/food/insert-meal", meal_data)
            status = "✅ 저장 완료" if api_result and "error" not in str(api_result).lower() else "❌ 저장 실패"
            results.append({
                "status": status,
                "food": food,
                "grams": grams,
                "calories": calories,
                "api_result": api_result
            })

        # 한 \ 끼 요약
        meal_summary = {
            "총칼로리": round(total_calories, 1),
            "단백질": round(total_protein, 1),
            "탄수화물": round(total_carbs, 1),
            "지방": round(total_fat, 1)
        }

        now = datetime.now()
        today = now.date()
        meal_time_str = now.strftime("%p %I시 %M분").replace("AM", "오전").replace("PM", "오후")

        sql = f"""
            SELECT SUM(calories) as total_calories,
                SUM(protein) as total_protein,
                SUM(carbs) as total_carbs,
                SUM(fat) as total_fat
            FROM meal_records
            WHERE member_id = {member_id}
            AND meal_date = '{today}'
        """
        row = json.loads(execute_sql(sql))[0]
        nutrition_summary = {
            "총칼로리": round(row.get("total_calories", 0), 1),
            "단백질": round(row.get("total_protein", 0), 1),
            "탄수화물": round(row.get("total_carbs", 0), 1),
            "지방": round(row.get("total_fat", 0), 1)
        }

        nutrition_target = auto_nutrition_goal(member_id)
        nutrition_remaining = {
            "calories": round(nutrition_target["calories"] - nutrition_summary["총칼로리"], 1),
            "protein": round(nutrition_target["protein"] - nutrition_summary["단백질"], 1),
            "carbs": round(nutrition_target["carbs"] - nutrition_summary["탄수화물"], 1),
            "fat": round(nutrition_target["fat"] - nutrition_summary["지방"], 1)
        }
        nutrition_needed = nutrition_target.copy()

        # 식사 미리정보 문장
        meal_sentence = f"""
드시는 식사는  {len(food_names)}개 음식으로 구성되어 있고, 칼로리는 총 {meal_summary["총칼로리"]}kcal입니다.
단백질 {meal_summary["단백질"]}g, 탄수화물 {meal_summary["탄수화물"]}g, 지방 {meal_summary["지방"]}g가 포함되어 있어요.
""".strip()

        # LLM 피드백 포트 생성
        prompt = make_llm_feedback_prompt(nutrition_target, nutrition_summary, nutrition_remaining)
        feedback_text = llm.invoke(prompt).content.strip()

        final_feedback = f"{meal_sentence}\n\n{feedback_text}"

        return json.dumps({
            "meal_records": results,
            "meal_feedback": final_feedback,
            "nutrition_needed": nutrition_needed
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ 오류 발생: {str(e)}\n{traceback.format_exc()}"


@tool
def answer_general_nutrition_tool(params: dict) -> str:
    """
    하루 권장량, 영양소 기준 등 일반 영양 정보를 LLM과 웹검색을 통해 설명합니다.
    """
    question = params.get("input") or params.get("question", "")
    tavily_response = TavilySearchAPIRetriever(question);
    web_summary = tavily_response.content
    
    prompt = f"""
    아래 질문에 대해 한국인 기준으로 정확한 영양 정보 기준으로 답변해줘.
    웹검색 결과: {web_summary}
    를 토대로 하여 질문에 대한 답변을 작성해줘.
    질문: {question}
    """
    return llm.invoke([HumanMessage(content=prompt)]).content.strip()
 
@tool 
def smart_nutrition_resolver(params: dict) -> str: 
    """ 
    사용자의 영양/식단 관련 질문에 대해 자동으로 SQL/웹검색/LLM 응답을 판단 및 실행하고, 
    confidence가 낮을 경우 재판단까지 포함하여 최적의 결과를 반환합니다. 
    """ 
    try: 
        question = params.get("input") or params.get("question", "")
        member_id = params.get("member_id", 1) 
        table_info = json.dumps(table_schema, ensure_ascii=False)

        def run_decision(prompt: str) -> dict:
            raw = llm.invoke([HumanMessage(content=prompt)]).content
            return json.loads(extract_json_block(raw))

        # Step 1: 응답 방식 판단
        decision_prompt = f"""
        너는 지능형 식단 응답 판단기야.
        사용자 질문을 보고 아래 중 어떤 응답 방식이 가장 적절한지 판단해줘.

        [선택지]
        - "sql": 질문이 DB에 저장된 정보를 기반으로 답변해야 하는 경우
        - "search": 최신 정보나 외부 지식이 필요한 경우
        - "llm": 일반 상식이나 유추 가능한 경우, LLM만으로 충분한 경우

        [출력 형식]
        - action: 선택한 방식 (sql / search / llm 중 하나)
        - reason: 왜 그렇게 판단했는지 간결한 설명
        - confidence: 확신 정도 (0 ~ 1 float)

        [테이블 스키마]
        {table_info}

        [사용자 질문]
        "{question}"

        [출력 예시]
        {{
        "action": "sql",
        "reason": "알레르기 정보는 DB에 저장된 사용자 데이터를 조회해야 하기 때문",
        "confidence": 0.92
        }}
        """

        decision = run_decision(decision_prompt)
        action = decision.get("action")
        reason = decision.get("reason", "")
        confidence = float(decision.get("confidence", 1.0))

        # 낮은 확신이면 1회 재시도
        if confidence < 0.7:
            retry = run_decision(decision_prompt)
            action = retry.get("action")
            reason = retry.get("reason", "")
            confidence = float(retry.get("confidence", 1.0))

            if confidence < 0.7:
                action = "llm"
                reason += " (신뢰도 낮아 LLM 응답으로 fallback)"

        print(f"🧠 판단 결과: {action} | 이유: {reason} | 신뢰도: {confidence}")

        intermediate_result = ""
        data_source = ""

        if action == "sql":
            sql_prompt = f"""
            너는 SQL 생성 전문가야. 아래 기준을 철저히 지켜서 SQL SELECT 문을 만들어줘.

            [사용자 질문]
            "{question}"

            [제약 조건]
            1. 반드시 SQL SELECT 문 하나만 출력해. 설명이나 주석은 절대 금지.
            2. WHERE 절에 반드시 "member_id = {member_id}" 조건을 포함해야 해.
            3. 필요한 컬럼만 선택하고, * 사용 금지.
            4. 조인은 꼭 필요할 때만 써.
            5. 테이블 스키마 외 테이블은 사용 금지.

            [테이블 스키마]
            {table_info}
            """
            sql = llm.invoke([HumanMessage(content=sql_prompt)]).content.strip()
            result = execute_sql(sql)
            intermediate_result = json.dumps(result, ensure_ascii=False)
            data_source = "sql"

        elif action == "search":
            search_result = TavilySearchAPIRetriever.invoke(question)
            summary_prompt = f"""
            [사용자 질문]
            {question}

            [검색 결과]
            {search_result}

            위 내용을 바탕으로 요약 + 설명 + 링크를 포함한 응답을 자연스럽게 작성해줘.
            """
            refined = llm.invoke([HumanMessage(content=summary_prompt)]).content.strip()
            return json.dumps({
                "source": "web",
                "final_answer": refined,
                "reason": reason,
                "confidence": confidence
            }, ensure_ascii=False, indent=2)

        elif action == "llm":
            llm_prompt = f"""
            너는 식단/영양 전문가야.
            아래 질문에 대해 한국 기준(KDRI 등)으로 정리된 구조화된 응답을 해줘.

            [질문]
            {question}

            [응답 양식]
            1. 📌 질문 요약
            2. 📊 한국 기준 정리
            3. 🧠 전문가 설명
            4. 🔍 정보 출처

            ⚠️ 기준이 없으면 "일반적인 경향"으로 설명해줘.
            """
            refined = llm.invoke([HumanMessage(content=llm_prompt)]).content.strip()
            return json.dumps({
                "source": "llm",
                "final_answer": refined,
                "reason": reason,
                "confidence": confidence
            }, ensure_ascii=False, indent=2)

        # Step 3: 정제 응답
        refine_prompt = f"""
        사용자 질문: {question}
        중간 결과:
        {intermediate_result}

        위 정보를 바탕으로 한국 기준으로 자연스럽고 정확한 식단/영양 응답을 작성해줘.
        """
        refined = llm.invoke([HumanMessage(content=refine_prompt)]).content.strip()

        return json.dumps({
            "source": data_source,
            "final_answer": refined,
            "reason": reason,
            "confidence": confidence
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "❌ 오류 발생",
            "error": str(e)
        }, ensure_ascii=False, indent=2)

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
    answer_general_nutrition_tool,
    smart_nutrition_resolver,
]
 