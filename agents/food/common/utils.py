from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv
import os
import json
from datetime import date, datetime, timedelta
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage


from agents.food.common.db import (
    get_db_connection,
    get_user_info,
    get_food_nutrition,
    save_meal_record,
    get_today_meals,
    get_weekly_meals,
    get_diet_plan,
    get_user_preferences_db
)

# Docker에서 실행 중인 Qdrant 클라이언트 초기화 
client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 환경 변수 로드
load_dotenv()

def calculate_tdee(bmr: float, activity_level: str) -> float:
    """총 일일 에너지 소비량(TDEE) 계산"""
    activity_multipliers = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very_active': 1.9
    }
    return bmr * activity_multipliers.get(activity_level.lower(), 1.2)

def get_nutrient_ratios(goal: str) -> Dict[str, float]:
    """목표별 영양소 비율 설정"""
    ratios = {
        'diet': {'protein': 0.4, 'carbs': 0.3, 'fats': 0.3},
        'bulking': {'protein': 0.3, 'carbs': 0.5, 'fats': 0.2},
        'maintenance': {'protein': 0.3, 'carbs': 0.4, 'fats': 0.3}
    }
    return ratios.get(goal.lower(), ratios['maintenance'])

def search_food_info(query: str) -> Dict[str, Any]:
    """Tavily API를 사용하여 식품 정보 검색"""
    api_key = os.getenv('TAVILY_API_KEY')
    url = "https://api.tavily.com/search"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "query": f"nutrition information for {query}",
        "search_depth": "advanced",
        "include_answer": True,
        "include_domains": ["nutritionix.com", "fdc.nal.usda.gov"]
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()

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

def calculate_bmi(weight: float, height: float) -> float:
    """BMI 계산 (체중kg / 신장m^2)"""
    height_m = height / 100
    return weight / (height_m * height_m)

def calculate_bmr(user_data: Dict[str, Any]) -> float:
    """기초 대사량(BMR) 계산"""
    if user_data["gender"] == "남성":
        return 66 + (13.7 * user_data["weight"]) + (5 * user_data["height"]) - (6.8 * user_data["age"])
    else:
        return 655 + (9.6 * user_data["weight"]) + (1.8 * user_data["height"]) - (4.7 * user_data["age"])

def analyze_weekly_nutrition(weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """주간 영양소 분석"""
    total_nutrition = {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}
    meal_count = 0
    
    for meal in weekly_meals:
        if meal["nutrition"]:
            for nutrient, amount in meal["nutrition"].items():
                if nutrient in total_nutrition:
                    total_nutrition[nutrient] += amount
            meal_count += 1
    
    if meal_count > 0:
        for nutrient in total_nutrition:
            total_nutrition[nutrient] /= meal_count
    
    return total_nutrition

def get_nutrition_recommendations(user_info: Dict[str, Any], current_nutrition: Dict[str, float]) -> Dict[str, Any]:
    """영양소 추천"""
    # BMR과 TDEE 계산
    bmr = calculate_bmr(user_info)
    tdee = calculate_tdee(bmr, user_info["activity_level"])
    
    # 목표 영양소 계산
    ratios = get_nutrient_ratios(user_info["goal"])
    target_nutrition = calculate_nutrient_targets(tdee, ratios)
    
    # 결핍 영양소 분석
    deficiencies = analyze_nutrition(current_nutrition, target_nutrition)
    
    # 추천 식품 생성
    recommendations = {}
    for nutrient, amount in deficiencies.items():
        foods = recommend_foods({nutrient: amount})
        if foods:
            recommendations[nutrient] = foods
    
    return {
        "bmr": bmr,
        "tdee": tdee,
        "target_nutrition": target_nutrition,
        "deficiencies": deficiencies,
        "recommendations": recommendations
    }

def generate_meal_plan(user_info: Dict[str, Any], weekly_nutrition: Dict[str, float]) -> Dict[str, Any]:
    """맞춤형 식단 생성"""
    # 영양소 추천 받기
    nutrition_info = get_nutrition_recommendations(user_info, weekly_nutrition)
    
    # 식단 계획 생성
    diet_plan = get_diet_plan(user_info["goal"], user_info["gender"])
    if not diet_plan:
        return None
    
    # 식단에 추천 식품 추가
    for meal_type in ["breakfast", "lunch", "dinner"]:
        for nutrient, foods in nutrition_info["recommendations"].items():
            if foods:
                diet_plan["meals"][meal_type].append({
                    "name": foods[0]["name"],
                    "nutrition": foods[0]["nutrition"]
                })
    
    return {
        "diet_plan": diet_plan,
        "nutrition_info": nutrition_info
    }

def analyze_meal_input(user_id: int, meal_text: str) -> Dict[str, Any]:
    """식단 입력 분석"""
    # LLM으로 식단 분석
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = f"""
    다음 식단 입력을 분석해주세요:
    입력: {meal_text}
    
    다음 형식으로 JSON 응답을 제공해주세요:
    {{
        "meal_type": "아침/점심/저녁/간식",
        "foods": ["식품명"],
        "nutrition": {{
            "protein": 단백질량(g),
            "carbs": 탄수화물량(g),
            "fat": 지방량(g),
            "calories": 칼로리(kcal)
        }}
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        if isinstance(response, AIMessage):
            analysis = json.loads(response.content)
            
            # 식사 기록 저장
            if save_meal_record(user_id, analysis["meal_type"], analysis["foods"], analysis["nutrition"]):
                return {
                    "success": True,
                    "analysis": analysis
                }
    except Exception as e:
        print(f"식단 입력 분석 오류: {e}")
    
    return {
        "success": False,
        "error": "식단 입력 분석 실패"
    }

def calculate_nutrient_targets(tdee: float, ratios: Dict[str, float]) -> Dict[str, float]:
    """TDEE와 영양소 비율을 기반으로 목표 영양소량을 계산합니다."""
    protein_calories = tdee * ratios["protein"]
    carbs_calories = tdee * ratios["carbs"]
    fat_calories = tdee * ratios["fat"]
    
    return {
        "protein": protein_calories / 4,  # g
        "carbs": carbs_calories / 4,      # g
        "fat": fat_calories / 9           # g
    }

def recommend_foods_for_deficiency(deficiency: Dict[str, float]) -> Dict[str, List[Dict[str, Any]]]:
    """결핍 영양소에 대한 식품 추천"""
    recommendations = {}
    for nutrient, amount in deficiency.items():
        foods = search_food_info(f"{nutrient} 영양소가 풍부한 식품")
        if foods:
            recommendations[nutrient] = foods
    return recommendations
 
def get_user_preferences(user_id: int) -> Dict[str, Any]:
    """사용자의 식단 선호도를 조회합니다."""
    return get_user_preferences_db(user_id)
 
def calculate_age(birth_date: date) -> int:
    """생년월일로 나이 계산"""
    today = date.today()
    
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
        
    return age
