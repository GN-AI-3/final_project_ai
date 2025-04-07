from typing import Dict, Any
from common.db import get_today_meals
from common.utils import search_food_info, analyze_nutrition, recommend_foods

def check_deficiency_tool(user_id: int, target_nutrition: Dict[str, float]) -> Dict[str, Any]:
    """영양소 결핍 확인 도구"""
    try:
        # 오늘의 식사 조회
        meals = get_today_meals(user_id)
        
        # 현재 영양소 계산
        current_nutrition = {
            "protein": 0,
            "carbs": 0,
            "fats": 0
        }
        
        for meal in meals:
            food_info = search_food_info(meal["food_name"])
            portion = meal["portion"]
            
            current_nutrition["protein"] += food_info.get("protein", 0) * portion / 100
            current_nutrition["carbs"] += food_info.get("carbs", 0) * portion / 100
            current_nutrition["fats"] += food_info.get("fats", 0) * portion / 100
        
        # 결핍 분석
        deficiencies = analyze_nutrition(current_nutrition, target_nutrition)
        
        return {
            "current_nutrition": current_nutrition,
            "target_nutrition": target_nutrition,
            "deficiencies": deficiencies
        }
    except Exception as e:
        print(f"영양소 결핍 확인 중 오류 발생: {e}")
        return None

def recommend_foods_tool(deficiencies: Dict[str, float]) -> Dict[str, Any]:
    """식품 추천 도구"""
    try:
        # 부족한 영양소 기반 식품 추천
        recommendations = recommend_foods(deficiencies)
        
        return {
            "deficiencies": deficiencies,
            "recommendations": recommendations
        }
    except Exception as e:
        print(f"식품 추천 중 오류 발생: {e}")
        return None 