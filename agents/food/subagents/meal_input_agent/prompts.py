from typing import Dict, Any, List
import json

def get_input_analysis_prompt(user_input: str) -> str:
    """입력 분석 프롬프트 생성"""
    return f"""
    다음 사용자 입력을 분석하여 식단 정보를 추출해주세요.
    입력에 식사 유형(아침, 점심, 저녁, 간식)이 명시되지 않은 경우, 현재 시간을 기준으로 자동으로 결정해주세요.
    
    입력: {user_input}
    
    다음 JSON 형식으로 응답해주세요:
    {{
        "intent": "식단 입력 또는 식단 조회",
        "meal_type": "아침, 점심, 저녁, 간식 중 하나",
        "foods": ["음식1", "음식2", ...],
        "date": "YYYY-MM-DD" (입력이 없는 경우 오늘 날짜)
    }}
    
    예시:
    입력: "아침 바나나"
    응답: {{
        "intent": "식단 입력",
        "meal_type": "아침",
        "foods": ["바나나"],
        "date": "2024-04-03"
    }}
    
    입력: "바나나 먹었어"
    응답: {{
        "intent": "식단 입력",
        "meal_type": "아침",  // 현재 시간이 아침인 경우
        "foods": ["바나나"],
        "date": "2024-04-03"
    }}
    """

def get_nutrition_analysis_prompt(foods: List[str], nutrition_info: List[Dict[str, Any]]) -> str:
    """영양소 분석 프롬프트 생성"""
    return f"""
    다음 식단의 영양소를 분석하고 부족한 영양소와 추천 식품을 알려주세요.
    
    식단: {', '.join(foods)}
    영양소 정보: {json.dumps(nutrition_info, ensure_ascii=False)}
    
    다음 형식으로 응답해주세요:
    {{
        "analysis": "영양소 분석 결과",
        "missing_nutrients": ["부족한 영양소1", "부족한 영양소2", ...],
        "recommendations": ["추천 식품1", "추천 식품2", ...]
    }}
    """

def get_weekly_analysis_prompt(user_info: Dict[str, Any], weekly_nutrition: Dict[str, float]) -> str:
    """주간 분석 프롬프트 생성"""
    return f"""
    다음 사용자의 주간 영양소 섭취를 분석하고 개선점을 제안해주세요.
    
    사용자 정보: {json.dumps(user_info, ensure_ascii=False)}
    주간 영양소: {json.dumps(weekly_nutrition, ensure_ascii=False)}
    
    다음 형식으로 응답해주세요:
    {{
        "analysis": "주간 영양소 분석 결과",
        "improvements": ["개선점1", "개선점2", ...],
        "recommendations": ["추천 식품1", "추천 식품2", ...]
    }}
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

def get_today_meals_prompt(meals: List[Dict[str, Any]]) -> str:
    """오늘의 식사 조회 프롬프트"""
    return f"""
    다음 오늘의 식사 정보를 분석해주세요:
    
    식사 정보: {meals}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "meals": [
            {{
                "time": "식사 시간",
                "food": {{
                    "name": "식품명",
                    "portion": "섭취량",
                    "nutrition": {{
                        "protein": "단백질량",
                        "carbs": "탄수화물량",
                        "fats": "지방량"
                    }}
                }}
            }}
        ]
    }}
    """ 