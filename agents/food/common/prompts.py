from typing import Dict, Any

def get_analyze_input_prompt(message: str) -> str:
    """입력 분석 프롬프트"""
    return f"""
    다음 사용자 입력을 분석하여 의도를 파악하고 필요한 정보를 추출해주세요.
    
    입력: {message}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "intent": "식사 기록" | "식단 추천" | "영양소 분석",
        "meal_time": "아침" | "점심" | "저녁" | "간식",
        "food_name": "식품명 (식사 기록인 경우)",
        "portion": "섭취량 (식사 기록인 경우)",
        "additional_info": {{
            "goal": "목표 (식단 추천인 경우)",
            "preferences": ["선호하는 음식", "알레르기 등"],
            "restrictions": ["제한해야 하는 음식", "알레르기 등"]
        }}
    }}
    
    주의사항:
    1. intent는 반드시 "식사 기록", "식단 추천", "영양소 분석" 중 하나여야 합니다.
    2. meal_time은 반드시 "아침", "점심", "저녁", "간식" 중 하나여야 합니다.
    3. 식사 기록인 경우 food_name과 portion을 반드시 포함해야 합니다.
    4. 식단 추천인 경우 additional_info에 goal을 반드시 포함해야 합니다.
    """

def get_meal_record_prompt(food_info: Dict[str, Any]) -> str:
    """식사 기록 프롬프트"""
    return f"""
    다음 식품 정보를 바탕으로 식사 기록을 생성해주세요:
    
    식품 정보: {food_info}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "food_name": "식품명",
        "portion": "섭취량",
        "nutrition": {{
            "protein": "단백질량",
            "carbs": "탄수화물량",
            "fats": "지방량"
        }}
    }}
    """

def get_nutrition_analysis_prompt(current_nutrition: Dict[str, float], target_nutrition: Dict[str, float]) -> str:
    """영양소 분석 프롬프트"""
    return f"""
    현재 영양소 섭취량과 목표 영양소 섭취량을 비교하여 분석해주세요:
    
    현재 영양소:
    {current_nutrition}
    
    목표 영양소:
    {target_nutrition}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "deficiencies": {{
            "영양소명": "부족량"
        }},
        "recommendations": {{
            "영양소명": [
                {{
                    "food_name": "추천 식품명",
                    "nutrition": {{
                        "영양소명": "함유량"
                    }}
                }}
            ]
        }}
    }}
    """


def get_meal_plan_prompt(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any]) -> str:
    """식단 계획 프롬프트"""
    return f"""
    사용자 정보와 영양소 계획을 바탕으로 맞춤형 식단을 생성해주세요:
    
    사용자 정보:
    {user_info}
    
    영양소 계획:
    {nutrition_plan}
    
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
        "snacks": [...]
    }}
    """ 