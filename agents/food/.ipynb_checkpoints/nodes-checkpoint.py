import json
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from .prompts import MEAL_PLANNING_PROMPT
from .utils import (
    calculate_bmr,
    calculate_tdee,
    analyze_food_nutrition,
    get_food_info,
    search_vector_db,
    search_web_info,
    calculate_bmi
)


class UserState(TypedDict, total=False):
    user_data: Dict[str, Any]
    current_action: str
    messages: List[Any]
    context: Dict[str, Any]
    bmr: float
    tdee: float
    bmi: float
    bmi_status: str
    nutrition_plan: Dict[str, Any]
    meal_plan: List[Dict[str, Any]]
    food_info: Dict[str, Any]
    data_quality: Dict[str, Any]
    nutrition_analysis: Dict[str, Any]
    supplement_recommendations: List[Dict[str, Any]]

def nutrition_calculation_node(state: UserState) -> UserState:
    """
    사용자의 영양소 요구사항을 계산하는 노드
    1. BMR 계산
    2. TDEE 계산
    3. 목표에 따른 칼로리 조정
    4. 영양소 비율 계산 (단백질 30%, 탄수화물 40%, 지방 30%)
    """
    user_data = state["user_data"]
    bmr = calculate_bmr(
        user_data["weight"],
        user_data["height"],
        user_data["age"],
        user_data["gender"]
    )
    tdee = calculate_tdee(bmr, user_data["activity_level"])
    
    state["bmr"] = bmr
    state["tdee"] = tdee
    
    # 목표에 따른 영양소 계산
    goal = user_data.get("goal", "체중 유지")
    if goal == "체중 감량":
        target_calories = tdee - 500  # 하루 500칼로리 감소
    elif goal == "체중 증가":
        target_calories = tdee + 500  # 하루 500칼로리 증가
    else:
        target_calories = tdee
    
    # 영양소 목표 설정
    state["nutrition_plan"] = {
        "daily_calories": target_calories,
        "protein": (target_calories * 0.3) / 4,  # 30% 단백질 (1g = 4칼로리)
        "carbs": (target_calories * 0.4) / 4,    # 40% 탄수화물 (1g = 4칼로리)
        "fat": (target_calories * 0.3) / 9,      # 30% 지방 (1g = 9칼로리)
        "target_foods": user_data.get("target_foods", [])  # 사용자가 입력한 음식 목록
    }
    
    return state

def meal_planning_node(state: UserState, llm) -> UserState:
    """
    식단 계획을 생성하는 노드
    1. 입력된 음식들의 영양소 분석
    2. 목표 영양소와 비교하여 적절한 양 계산
    3. LLM을 사용하여 맞춤형 식단 계획 생성
    """
    nutrition_plan = state["nutrition_plan"]
    target_foods = nutrition_plan["target_foods"]
    
    # 각 음식의 영양소 분석
    food_analysis = []
    for food in target_foods:
        nutrition = analyze_food_nutrition(food)
        food_analysis.append({
            "name": food,
            "nutrition": nutrition
        })
    
    try:
        # LLM 호출 및 토큰 사용량 확인
        response = llm.generate([[AIMessage(content=MEAL_PLANNING_PROMPT.format(
            goal=state["user_data"]["goal"],
            calories=nutrition_plan["daily_calories"],
            protein=nutrition_plan["protein"],
            carbs=nutrition_plan["carbs"],
            fat=nutrition_plan["fat"],
            activity_level=state["user_data"]["activity_level"],
            food_analysis=json.dumps(food_analysis, ensure_ascii=False)
        ))]])

        # 응답 객체 출력 (디버깅 용)
        print(response)
        
        # 토큰 사용량 출력
        print("\n=== LLM 토큰 사용량 ===")
        if 'token_usage' in response.llm_output:
            print(f"- 프롬프트 토큰: {response.llm_output['token_usage']['prompt_tokens']}")
            print(f"- 완료 토큰: {response.llm_output['token_usage']['completion_tokens']}")
            print(f"- 총 토큰: {response.llm_output['token_usage']['total_tokens']}")
        else:
            print("토큰 사용량 정보가 없습니다.")
        
        # 응답 내용 출력
        print("\n=== LLM 응답 ===")
        print(response.generations[0][0].text)
        
    except Exception as e:
        print(f"LLM 처리 중 오류 발생: {e}")
        state["meal_plan"] = []

    return state

def vector_search_node(state: UserState) -> UserState:
    """벡터 DB에서 식품 정보 검색"""
    food_info = {}
    for food in state["user_data"]["target_foods"]:
        result = search_vector_db(food)
        if result:
            food_info[food] = result
    state["food_info"] = food_info
    return state

def evaluate_data_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """데이터 품질 평가"""
    food_info = state.get("food_info", {})
    is_reliable = all(
        food in food_info and food_info[food].get("confidence", 0) > 0.8
        for food in state["user_data"]["target_foods"]
    )
    state["data_quality"] = {"is_reliable": is_reliable}
    return state

def self_rag_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """Self-RAG를 통한 추가 정보 검색"""
    food_info = state.get("food_info", {})
    for food in state["user_data"]["target_foods"]:
        if food not in food_info or food_info[food].get("confidence", 0) <= 0.8:
            web_info = search_web_info(food)
            if web_info:
                food_info[food] = web_info
    state["food_info"] = food_info
    return state

def bmi_calculation_node(state: UserState) -> UserState:
    """BMI 계산"""
    height = state["user_data"]["height"]  # cm
    weight = state["user_data"]["weight"]  # kg
    bmi = calculate_bmi(weight, height)
    
    # BMI 상태 판정
    if bmi < 18.5:
        status = "저체중"
    elif bmi < 23:
        status = "정상"
    elif bmi < 25:
        status = "과체중"
    else:
        status = "비만"
    
    state["bmi"] = bmi
    state["bmi_status"] = status
    return state

def nutrition_analysis_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """영양소 분석"""
    food_info = state["food_info"]
    goal = state["user_data"]["goal"]
    bmi_status = state["bmi_status"]
    
    # 영양소 분석 프롬프트 생성
    analysis_prompt = f"""
    사용자 정보:
    - BMI 상태: {bmi_status}
    - 목표: {goal}
    
    섭취 식품:
    {food_info}
    
    위 정보를 바탕으로 영양소를 분석하고, 부족한 영양소를 파악해주세요.
    """
    
    response = llm.invoke(analysis_prompt)
    
    # 응답을 파싱하여 영양 분석 결과 저장
    state["nutrition_analysis"] = {
        "evaluation": response.content,
        "deficient_nutrients": ["단백질", "비타민C"]  # 예시, 실제로는 LLM 응답에서 파싱
    }
    return state

def recommend_supplements_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """부족한 영양소를 보충할 수 있는 식품 추천"""
    deficient_nutrients = state["nutrition_analysis"]["deficient_nutrients"]
    
    # 추천 프롬프트 생성
    recommend_prompt = f"""
    부족한 영양소:
    {deficient_nutrients}
    
    위 영양소를 보충할 수 있는 식품을 추천해주세요.
    각 식품에 대해 선택 이유도 설명해주세요.
    """
    
    response = llm.invoke(recommend_prompt)
    
    # 응답을 파싱하여 추천 식품 저장
    state["supplement_recommendations"] = [
        {"name": "닭가슴살", "reason": "단백질이 풍부함"},
        {"name": "오렌지", "reason": "비타민C가 풍부함"}
    ]  # 예시, 실제로는 LLM 응답에서 파싱
    return state
