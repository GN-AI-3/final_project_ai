from datetime import datetime
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from langchain.tools import Tool
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
from .api_client import FoodAPIClient

# API 클라이언트 인스턴스 생성
api_client = FoodAPIClient()

class UserInfo(BaseModel):
    """사용자 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    member_id: int
    name: str
    gender: str
    height: float
    weight: float
    birth: datetime   
    goal: str
    activity_level: str
    allergies: List[str]
    dietary_preference: str
    meal_pattern: str
    meal_times: List[str]
    food_preferences: List[str]
    special_requirements: List[str]

class FoodNutrition(BaseModel):
    """식품 영양소 정보 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    serving_size: float
    serving_unit: str

class MealRecord(BaseModel):
    """식사 기록 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    user_id: int
    food_name: str
    portion: float
    unit: str
    meal_type: str
    calories: float
    protein: float
    carbs: float
    fat: float
    created_at: datetime

class DietPlan(BaseModel):
    """식단 계획 모델"""
    model_config = ConfigDict(validate_by_name=True)
    
    diet_type: str
    user_gender: str
    meal_plan: Dict[str, List[Dict[str, Any]]]
    nutrition_goals: Dict[str, float]

class FoodSearchTool(Tool):
    name = "FoodSearchTool"
    description = "Use this tool to search for food information"

    async def _run(self, query: str) -> str:
        # This is a placeholder implementation. In a real-world scenario,
        # you would use a search engine or a database to find food information
        # based on the query.
        return f"Found food information for: {query}"

@Tool
def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    """사용자 정보 조회"""
    return api_client.get_user_info(user_id)

def get_food_nutrition(food_name: str) -> Optional[Dict[str, Any]]:
    """식품 영양소 정보 조회"""
    return api_client.get_food_nutrition(food_name)

def save_meal_record(
    user_id: int,
    meal_type: str,
    food_name: str,
    portion: float,
    unit: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float
) -> bool:
    """식사 기록 저장"""
    meal_data = {
        "memberId": user_id,
        "foodName": food_name,
        "portion": portion,
        "unit": unit,
        "mealType": meal_type,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat
    }
    return api_client.save_meal_record(meal_data)

def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    """오늘의 식사 기록 조회"""
    return api_client.get_today_meals(user_id)

def get_weekly_meals(user_id: int) -> List[Dict[str, Any]]:
    """주간 식사 기록 조회"""
    return api_client.get_weekly_meals(user_id)

def get_diet_plan(diet_type: str, user_gender: str) -> Optional[Dict[str, Any]]:
    """식단 계획 조회"""
    return api_client.get_diet_plan(diet_type, user_gender)

def get_user_preferences_db(user_id: int) -> Dict[str, Any]:
    """사용자 선호도 조회"""
    return api_client.get_user_preferences(user_id)

def analyze_weekly_nutrition(weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """주간 영양소 분석"""
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    for meal in weekly_meals:
        total_calories += meal.get("calories", 0)
        total_protein += meal.get("protein", 0)
        total_carbs += meal.get("carbs", 0)
        total_fat += meal.get("fat", 0)
    
    return {
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat,
        "average_daily_calories": total_calories / 7,
        "average_daily_protein": total_protein / 7,
        "average_daily_carbs": total_carbs / 7,
        "average_daily_fat": total_fat / 7
    }

async def recommend_foods(user_id: int) -> Dict[str, Any]:
    """음식 추천"""
    return api_client.recommend_foods(user_id)


 
