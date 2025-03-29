import json
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

 
from .prompts import NUTRITION_ANALYSIS_PROMPT, SUPPLEMENT_RECOMMENDATION_PROMPT, MEAL_PLANNING_PROMPT   

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
def meal_planning_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """
    식단 계획을 생성하는 노드
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
    
    # food_analysis를 문자열로 변환 (JSON 대신 텍스트 형식으로)
    food_analysis_text = "\n".join([f"음식: {item['name']}, 영양소: {item['nutrition']}" for item in food_analysis])
    
    # LLM을 사용한 프롬프트 생성
    prompt = MEAL_PLANNING_PROMPT.format(
        goal=state["user_data"]["goal"],
        calories=nutrition_plan["daily_calories"],
        protein=nutrition_plan["protein"],
        carbs=nutrition_plan["carbs"],
        fat=nutrition_plan["fat"],
        activity_level=state["user_data"]["activity_level"],
        food_analysis=food_analysis_text  # 여기서 food_analysis를 텍스트로 전달
    )
    
    try:
        # LLM 호출
        response = llm.invoke(prompt)
        
        # 응답 내용 확인
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        if not response_text.strip():  # 응답 내용이 비어있다면
            print("응답 내용이 비어 있습니다.")
            state["meal_plan"] = []
            return state
        
        # 응답 내용 출력 (디버깅 용)
        print("\n=== LLM 응답 ===")
        print(response_text)
        
        # 응답을 텍스트 형식으로 저장 후, 파싱을 통해 리스트로 변환
        # 예상되는 형태로 출력된 식단 데이터를 파싱합니다.
        try:
            # 여기에 응답을 파싱하는 로직을 추가합니다.
            # 예: 'meal_plan'이 리스트 형태여야 할 경우, JSON 형식으로 파싱
            meal_plan = json.loads(response_text.strip())  # 텍스트를 JSON으로 파싱
            if isinstance(meal_plan, list):  # 식단 계획이 리스트 형식인지 확인
                state["meal_plan"] = meal_plan
            else:
                # 리스트 형식이 아니면 오류 메시지 출력
                print("식단 계획이 리스트 형식이 아닙니다.")
                state["meal_plan"] = []
        except json.JSONDecodeError:
            # 응답이 JSON 형식이 아닐 경우, 텍스트로 저장
            print("식단 계획이 JSON 형식이 아닙니다. 텍스트로 저장합니다.")
            state["meal_plan"] = response_text.strip()
        
    except Exception as e:
        print(f"식단 계획 생성 중 오류 발생: {e}")
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
    """
    데이터 신뢰도 평가 노드
    """
    # 벡터 검색 결과 평가
    food_info = state.get("food_info", {})
    confidence = 0.0
    
    for food_name, info in food_info.items():
        if all(info.get(key, 0) > 0 for key in ["calories", "protein", "carbs", "fat"]):
            confidence += 1.0
    
    # 전체 식품 수로 나누어 평균 신뢰도 계산
    if food_info:
        confidence = confidence / len(food_info)
    
    # 신뢰도 정보 저장
    state["confidence"] = confidence
    state["data_quality"] = {
        "is_reliable": confidence > 0.8,
        "confidence_score": confidence
    }
    
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
    try:
        food_info = state["food_info"]
        goal = state["user_data"]["goal"]
        bmi_status = state["bmi_status"]
        
        # 사용자 정보를 기반으로 필요한 값들 추출
        daily_calories = state["user_data"].get("daily_calories", 0)  # 일일 필요 열량
        protein = state["user_data"].get("protein", 0)  # 단백질 필요량
        carbs = state["user_data"].get("carbs", 0)  # 탄수화물 필요량
        fat = state["user_data"].get("fat", 0)  # 지방 필요량
        activity_level = state["user_data"].get("activity_level", "보통")  # 활동 수준
        
        # 영양소 분석 프롬프트 생성 (NUTRITION_ANALYSIS_PROMPT 사용)
        analysis_prompt = NUTRITION_ANALYSIS_PROMPT.format(
            bmi_status=bmi_status,
            goal=goal,
            daily_calories=daily_calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            activity_level=activity_level,
            food_info=food_info
        )
        
        # LLM 응답 받기
        response = llm.invoke(analysis_prompt)
        
        # 응답이 비어있는지 확인
        response_text = response.content if hasattr(response, 'content') else str(response)
        if not response_text.strip():  # 응답 내용이 비어있다면
            print("응답 내용이 비어 있습니다.")
            state["nutrition_analysis"] = {}
            return state
        
        # 응답 내용을 출력
        print("\n=== LLM 응답 ===")
        print(response_text)
        
        # 응답을 파싱하여 부족한 영양소 추출하는 로직 추가
        # 예시로 "단백질"과 "비타민C"를 부족한 영양소로 가정, 실제로는 LLM 응답에서 추출 필요
        deficient_nutrients = extract_deficient_nutrients(response_text)
        
        # 영양 분석 결과 상태에 저장
        state["nutrition_analysis"] = {
            "evaluation": response_text,  # 전반적인 영양 상태 평가 내용
            "deficient_nutrients": deficient_nutrients  # LLM 응답에서 부족한 영양소 추출
        }
    
    except Exception as e:
        print(f"영양소 분석 중 오류 발생: {e}")
        state["nutrition_analysis"] = {}
    
    return state

def extract_deficient_nutrients(response_text: str) -> list:
    """
    LLM 응답에서 부족한 영양소를 추출하는 함수
    실제로는 LLM 응답을 파싱하여 부족한 영양소 리스트를 반환하도록 작성해야 함
    """
    # 부족한 영양소를 담을 리스트
    deficient_nutrients = []

    # 영양소 목록 (여기서는 예시로 몇 가지 영양소를 나열)
    nutrients = [
        "단백질", "비타민 C", "철분", "칼슘", "비타민 D", "엽산", "비타민 B12", "마그네슘", "아연",
        "비타민 A", "비타민 E", "오메가-3 지방산", "비타민 K", "구리", "망간", "나트륨", "칼륨"
    ]
    
    # 각 영양소에 대해 응답 텍스트에 부족 여부를 확인
    for nutrient in nutrients:
        # 예시: 영양소가 "부족하다" 또는 "현재 섭취량이 부족" 등의 문구가 포함되어 있는지 확인
        if nutrient in response_text and ("부족" in response_text or "현재 섭취량이 부족" in response_text):
            deficient_nutrients.append(nutrient)
    
    return deficient_nutrients

def recommend_supplements_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """
    부족한 영양소를 보완할 수 있는 식품을 추천하는 노드
    """
    deficient_nutrients = state.get("nutrition_analysis", {}).get("deficient_nutrients", [])
    if not deficient_nutrients:
        state["supplement_recommendations"] = []
        return state
    
    # 부족한 영양소 정보를 프롬프트에 포함
    prompt = SUPPLEMENT_RECOMMENDATION_PROMPT.format(
        deficient_nutrients=", ".join(deficient_nutrients),
        nutrition_analysis=json.dumps(state.get("nutrition_analysis", {}), ensure_ascii=False)
    )
    
    try:
        # LLM 호출
        response = llm.invoke(prompt)
        
        # 응답이 비어있는지 확인
        response_text = response.content if hasattr(response, 'content') else str(response)
        if not response_text.strip():  # 응답 내용이 비어있다면
            state["supplement_recommendations"] = []
            return state
        
        # 응답 내용을 로그로 출력
        print("\n=== LLM 응답 ===")
        print(response_text)
        
        # 보완 식품 추천 정보 형식에 맞게 리스트로 저장
        supplement_recommendations = []
        for line in response_text.split("\n"):
            if line.strip():  # 각 추천 항목을 리스트로 분리
                supplement_recommendations.append({
                    'name': line.strip().split(":")[0],  # 예시로 이름만 추출
                    'reason': line.strip().split(":")[1] if len(line.split(":")) > 1 else "정보 없음",  # 이유 추출
                    'nutrition': '정보 없음'  # 영양소는 기본값 "정보 없음"
                })
        
        state["supplement_recommendations"] = supplement_recommendations
        
    except Exception as e:
        print(f"보완 식품 추천 중 오류 발생: {e}")
        state["supplement_recommendations"] = []
    
    return state