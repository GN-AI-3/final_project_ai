from typing import Dict, Any
from common.db import get_diet_plan
from common.utils import calculate_bmr, calculate_tdee, get_nutrient_ratios, search_food_info

def calculate_nutrition_plan_tool(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """영양소 계획 계산 도구"""
    try:
        # BMR 계산
        bmr = calculate_bmr(
            user_info["gender"],
            user_info["age"],
            user_info["height"],
            user_info["weight"]
        )
        
        # TDEE 계산
        tdee = calculate_tdee(bmr, user_info["activity_level"])
        
        # 영양소 비율 설정
        ratios = get_nutrient_ratios(user_info["goal"])
        
        # 목표 영양소량 계산
        target_nutrition = {
            "protein": (tdee * ratios["protein"]) / 4,  # 4kcal/g
            "carbs": (tdee * ratios["carbs"]) / 4,      # 4kcal/g
            "fats": (tdee * ratios["fats"]) / 9         # 9kcal/g
        }
        
        return {
            "bmr": bmr,
            "tdee": tdee,
            "ratios": ratios,
            "target_nutrition": target_nutrition
        }
    except Exception as e:
        print(f"영양소 계획 계산 중 오류 발생: {e}")
        return None

def generate_meal_plan_tool(user_info: Dict[str, Any], nutrition_plan: Dict[str, Any]) -> Dict[str, Any]:
    """식단 계획 생성 도구"""
    try:
        # 식단 유형 결정
        diet_type = "high_protein" if user_info["goal"] == "diet" else "balanced"
        
        # 식단 계획 조회
        diet_plan = get_diet_plan(diet_type, user_info["gender"])
        
        if not diet_plan:
            return None
        
        # 식단 영양소 계산
        meal_plan = {
            "diet_type": diet_type,
            "breakfast": [],
            "lunch": [],
            "dinner": [],
            "snacks": []
        }
        
        # 아침 식사
        for food in diet_plan["breakfast"].split(","):
            food_info = search_food_info(food.strip())
            meal_plan["breakfast"].append({
                "name": food.strip(),
                "portion": 100,
                "nutrition": {
                    "protein": food_info.get("protein", 0),
                    "carbs": food_info.get("carbs", 0),
                    "fats": food_info.get("fats", 0)
                }
            })
        
        # 점심 식사
        for food in diet_plan["lunch"].split(","):
            food_info = search_food_info(food.strip())
            meal_plan["lunch"].append({
                "name": food.strip(),
                "portion": 100,
                "nutrition": {
                    "protein": food_info.get("protein", 0),
                    "carbs": food_info.get("carbs", 0),
                    "fats": food_info.get("fats", 0)
                }
            })
        
        # 저녁 식사
        for food in diet_plan["dinner"].split(","):
            food_info = search_food_info(food.strip())
            meal_plan["dinner"].append({
                "name": food.strip(),
                "portion": 100,
                "nutrition": {
                    "protein": food_info.get("protein", 0),
                    "carbs": food_info.get("carbs", 0),
                    "fats": food_info.get("fats", 0)
                }
            })
        
        # 간식
        meal_plan["snacks"] = [
            {
                "name": "과일",
                "portion": 100,
                "nutrition": {
                    "protein": 0.5,
                    "carbs": 15,
                    "fats": 0.3
                }
            },
            {
                "name": "견과류",
                "portion": 30,
                "nutrition": {
                    "protein": 5,
                    "carbs": 5,
                    "fats": 15
                }
            }
        ]
        
        return meal_plan
    except Exception as e:
        print(f"식단 계획 생성 중 오류 발생: {e}")
        return None 