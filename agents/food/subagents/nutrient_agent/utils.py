from typing import Dict, Any, List

def analyze_nutrition(current: Dict[str, float], target: Dict[str, float]) -> Dict[str, float]:
    """영양소 결핍 분석"""
    deficiencies = {}
    for nutrient, target_amount in target.items():
        if nutrient in current:
            deficiency = target_amount - current[nutrient]
            if deficiency > 0:
                deficiencies[nutrient] = deficiency
    return deficiencies

def recommend_foods(deficiencies: Dict[str, float]) -> Dict[str, List[Dict[str, Any]]]:
    """부족한 영양소 기반 식품 추천"""
    recommendations = {}
    for nutrient, amount in deficiencies.items():
        recommendations[nutrient] = [
            {
                "name": f"{nutrient} rich food 1",
                "nutrition": {nutrient: amount * 1.5}
            },
            {
                "name": f"{nutrient} rich food 2",
                "nutrition": {nutrient: amount * 1.2}
            }
        ]
    return recommendations

def get_today_meals(user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """오늘의 식사 기록 조회"""
    # 임시 데이터 반환
    return [
        {
            "meal_type": "아침",
            "foods": ["밥", "김치", "계란"],
            "nutrition": {"탄수화물": 50.0, "단백질": 20.0, "지방": 10.0}
        },
        {
            "meal_type": "점심",
            "foods": ["밥", "된장국", "고기"],
            "nutrition": {"탄수화물": 60.0, "단백질": 30.0, "지방": 15.0}
        }
    ]

def get_weekly_meals(user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """주간 식사 기록 조회"""
    # 임시 데이터 반환
    return [
        {
            "date": "2024-03-20",
            "meals": get_today_meals(user_data)
        }
    ]

def analyze_weekly_nutrition(weekly_meals: List[Dict[str, Any]]) -> Dict[str, float]:
    """주간 영양소 분석"""
    total_nutrition = {}
    meal_count = 0
    
    for day in weekly_meals:
        for meal in day["meals"]:
            for nutrient, amount in meal["nutrition"].items():
                if nutrient not in total_nutrition:
                    total_nutrition[nutrient] = 0
                total_nutrition[nutrient] += amount
            meal_count += 1
    
    # 평균 계산
    if meal_count > 0:
        for nutrient in total_nutrition:
            total_nutrition[nutrient] /= meal_count
    
    return total_nutrition

def get_nutrition_recommendations(weekly_nutrition: Dict[str, float], target_nutrition: Dict[str, float]) -> Dict[str, Any]:
    """영양소 추천"""
    deficiencies = analyze_nutrition(weekly_nutrition, target_nutrition)
    recommendations = recommend_foods(deficiencies)
    
    return {
        "deficiencies": deficiencies,
        "recommendations": recommendations
    }

def analyze_meal_input(user_input: str) -> Dict[str, Any]:
    """식사 입력 분석"""
    # 임시 데이터 반환
    return {
        "meal_type": "간식",
        "foods": ["사과", "바나나"],
        "nutrition": {"탄수화물": 30.0, "단백질": 5.0, "지방": 2.0}
    } 