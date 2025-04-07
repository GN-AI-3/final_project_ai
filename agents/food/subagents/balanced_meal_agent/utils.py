from typing import Dict, Any
from langchain_openai import ChatOpenAI
from agents.food.common.db import get_db_connection

def classify_diet_type(user_info: Dict[str, Any]) -> str:
    """사용자 정보 기반으로 LLM을 통해 식단 추천"""
    llm = ChatOpenAI(model="gpt-4o-mini")
    
    prompt = f"""
    ### 사용자 정보 기반 식단 추천

    아래 사용자 정보를 바탕으로 6가지 식단 중 가장 적합한 식단을 선택하세요.

    **6가지 식단 유형**
    1. 다이어트 식단
    2. 벌크업 식단
    3. 체력 증진 식단
    4. 유지/균형 식단
    5. 고단백/저탄수화물 식단
    6. 고탄수/고단백 식단

    **사용자 정보**
    - 성별: {user_info['gender']}
    - 키: {user_info['height']} cm
    - 몸무게: {user_info['weight']} kg
    - 나이: {2025 - int(user_info['birth'].year)} 세
    - 목표: {user_info['goal']}
    - 활동 수준: {user_info['activity_level']}
    - 알러지 정보: {user_info['allergies']}
    - 식단 선호: {user_info['dietary_preference']}
    - 식사 패턴: {user_info['meal_pattern']}
    - 식사 시간: {user_info['meal_times']}
    - 음식 선호: {user_info['food_preferences']}
    - 특별 요청: {user_info['special_requirements']}

    위 정보를 바탕으로 가장 적합한 식단 유형을 하나만 선택해주세요.
    """
    
    response = llm.invoke(prompt)
    return response.content.strip()

def get_diet_plan_by_type(diet_type: str, user_gender: str) -> Dict[str, Any]:
    """식단 유형과 성별에 맞는 식단 계획 조회"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT * FROM diet_plans 
            WHERE diet_type = %s AND user_gender = %s
            ORDER BY RANDOM()
            LIMIT 1
        """, (diet_type, user_gender))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def calculate_bmr(user_info: Dict[str, Any]) -> float:
    """기초 대사량 계산"""
    weight = user_info['weight']
    height = user_info['height']
    age = 2025 - int(user_info['birth'].year)
    
    if user_info['gender'] == '남성':
        return 66 + (13.7 * weight) + (5 * height) - (6.8 * age)
    else:
        return 655 + (9.6 * weight) + (1.8 * height) - (4.7 * age)

def calculate_tdee(bmr: float, activity_level: str) -> float:
    """일일 에너지 소비량 계산"""
    activity_multipliers = {
        '매우 낮음': 1.2,
        '낮음': 1.375,
        '보통': 1.55,
        '높음': 1.725,
        '매우 높음': 1.9
    }
    return bmr * activity_multipliers.get(activity_level, 1.55)

def get_nutrient_ratios(diet_type: str) -> Dict[str, float]:
    """목표별 영양소 비율 계산"""
    ratios = {
        '다이어트 식단': {'protein': 0.4, 'carbs': 0.3, 'fat': 0.3},
        '벌크업 식단': {'protein': 0.3, 'carbs': 0.5, 'fat': 0.2},
        '체력 증진 식단': {'protein': 0.35, 'carbs': 0.45, 'fat': 0.2},
        '유지/균형 식단': {'protein': 0.3, 'carbs': 0.4, 'fat': 0.3},
        '고단백/저탄수화물 식단': {'protein': 0.5, 'carbs': 0.2, 'fat': 0.3},
        '고탄수/고단백 식단': {'protein': 0.4, 'carbs': 0.4, 'fat': 0.2}
    }
    return ratios.get(diet_type, {'protein': 0.3, 'carbs': 0.4, 'fat': 0.3})

def generate_meal_plan(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any]) -> Dict[str, Any]:
    """식단 계획 생성"""
    return {
        "diet_type": "balanced",
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    } 





