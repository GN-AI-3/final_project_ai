from typing import Dict, Any

def get_analyze_balanced_input_prompt(message: str) -> str:
    """맞춤형 식단 입력 분석 프롬프트"""
    return f"""
    다음 사용자 입력을 분석하여 맞춤형 식단 관련 정보를 추출해주세요:
    
    입력: {message}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "task": "generate_meal_plan",
        "goal": "diet" | "bulking" | "maintenance",
        "preferences": {{
            "allergies": ["알레르기"],
            "health_conditions": ["건강 상태"],
            "dietary_preferences": ["식사 선호도"],
            "meal_patterns": ["식사 패턴"],
            "meal_times": ["식사 시간"],
            "food_preferences": ["식품 선호도"],
            "special_requirements": ["특별 요구사항"]
        }}
    }}
    """

def get_nutrition_plan_prompt(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any]) -> str:
    """영양소 계획 프롬프트"""
    return f"""
    다음 사용자 정보와 영양소 계획을 분석해주세요:
    
    사용자 정보:
    {user_info}
    
    영양소 계획:
    {nutrition_plan}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "bmr": "기초 대사율",
        "tdee": "총 일일 에너지 소비량",
        "ratios": {{
            "protein": "단백질 비율",
            "carbs": "탄수화물 비율",
            "fats": "지방 비율"
        }},
        "target_nutrition": {{
            "protein": "목표 단백질량",
            "carbs": "목표 탄수화물량",
            "fats": "목표 지방량"
        }}
    }}
    """

def get_meal_plan_prompt(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any], meal_plan: Dict[str, Any]) -> str:
    """식단 계획 프롬프트"""
    return f"""
    다음 사용자 정보, 영양소 계획, 식단 계획을 분석해주세요:
    
    사용자 정보:
    {user_info}
    
    영양소 계획:
    {nutrition_plan}
    
    식단 계획:
    {meal_plan}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "diet_type": "식단 유형",
        "breakfast": [
            {{
                "food_name": "식품명",
                "portion": "섭취량",
                "nutrition": {{
                    "protein": "단백질량",
                    "carbs": "탄수화물량",
                    "fats": "지방량"
                }}
            }}
        ],
        "lunch": [...],
        "dinner": [...],
        "snacks": [...],
        "total_nutrition": {{
            "protein": "총 단백질량",
            "carbs": "총 탄수화물량",
            "fats": "총 지방량"
        }}
    }}
    """ 


def get_goal_meal_plan_prompt(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any], meal_plan: Dict[str, Any]) -> str:
    """목표에 맞는 식단 계획 프롬프트"""
    return f"""
 ### 사용자 정보 기반 식단 추천

    아래 사용자 정보를 바탕으로 6가지 식단 중 가장 적합한 식단을 선택하세요.

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

    **6가지 식단 유형**
    1. 다이어트 식단
    2. 벌크업 식단
    3. 체력 증진 식단
    4. 유지/균형 식단
    5. 고단백/저탄수화물 식단
    6. 고탄수/고단백 식단

    ### 출력 형식:
    ```json
    {{
      "diet_type": "선택된 식단 유형",
      "reason": "선택 이유"
    }}
    ```
    """
