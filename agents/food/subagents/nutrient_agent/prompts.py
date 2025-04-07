from typing import Dict, Any

def get_analyze_nutrient_input_prompt(message: str) -> str:
    """영양소 입력 분석 프롬프트"""
    return f"""
    다음 사용자 입력을 분석하여 영양소 관련 정보를 추출해주세요:
    
    입력: {message}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "task": "check_deficiency" | "recommend_foods",
        "target_nutrition": {{
            "protein": "목표 단백질량",
            "carbs": "목표 탄수화물량",
            "fats": "목표 지방량"
        }}
    }}
    """

def get_deficiency_analysis_prompt(current: Dict[str, float], target: Dict[str, float]) -> str:
    """영양소 결핍 분석 프롬프트"""
    return f"""
    다음 현재 영양소 섭취량과 목표 영양소 섭취량을 비교하여 분석해주세요:
    
    현재 영양소:
    {current}
    
    목표 영양소:
    {target}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "current_nutrition": {{
            "protein": "현재 단백질량",
            "carbs": "현재 탄수화물량",
            "fats": "현재 지방량"
        }},
        "target_nutrition": {{
            "protein": "목표 단백질량",
            "carbs": "목표 탄수화물량",
            "fats": "목표 지방량"
        }},
        "deficiencies": {{
            "protein": "단백질 부족량",
            "carbs": "탄수화물 부족량",
            "fats": "지방 부족량"
        }}
    }}
    """

def get_food_recommendation_prompt(deficiencies: Dict[str, float]) -> str:
    """식품 추천 프롬프트"""
    return f"""
    다음 부족한 영양소를 보완할 수 있는 식품을 추천해주세요:
    
    부족한 영양소:
    {deficiencies}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "deficiencies": {{
            "protein": "단백질 부족량",
            "carbs": "탄수화물 부족량",
            "fats": "지방 부족량"
        }},
        "recommendations": {{
            "protein": [
                {{
                    "food_name": "추천 식품명",
                    "nutrition": {{
                        "protein": "단백질 함유량",
                        "carbs": "탄수화물 함유량",
                        "fats": "지방 함유량"
                    }}
                }}
            ],
            "carbs": [...],
            "fats": [...]
        }}
    }}
    """ 