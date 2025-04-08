from datetime import datetime
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from langchain.tools import BaseTool
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
from .api_client import FoodAPIClient
from langchain.agents import initialize_agent, AgentType

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

class FoodSearchTool(BaseTool):
    """음식 검색 도구"""
    name: str = "FoodSearchTool"
    description: str = "음식 검색 도구"
    
    def _run(self, query: str) -> str:
        # 실제 구현 시 음식 검색 로직 추가
        return f"Found food information for: {query}"
        
    async def _arun(self, query: str) -> str:
        return await self._run(query)

class UserInfoTool(BaseTool):
    """사용자 정보 조회 도구"""
    name: str = "UserInfoTool"
    description: str = "사용자 정보를 조회하는 도구"
    
    def _run(self, user_id: int) -> Dict[str, Any]:
        return api_client.get_user_info(user_id)
        
    async def _arun(self, user_id: int) -> Dict[str, Any]:
        return self._run(user_id)

class FoodNutritionTool(BaseTool):
    """식품 영양소 정보 조회 도구"""
    name: str = "FoodNutritionTool"
    description: str = "식품의 영양소 정보를 조회하는 도구"
    
    def _run(self, food_name: str) -> Dict[str, Any]:
        return api_client.get_food_nutrition(food_name)
        
    async def _arun(self, food_name: str) -> Dict[str, Any]:
        return self._run(food_name)

class SaveMealRecordTool(BaseTool):
    """식사 기록 저장 도구"""
    name: str = "SaveMealRecordTool"
    description: str = "식사 기록을 저장하는 도구"
    
    def _run(self, user_id: int, meal_type: str, food_name: str, portion: float, 
            unit: str, calories: float, protein: float, carbs: float, fat: float) -> bool:
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
        
    async def _arun(self, user_id: int, meal_type: str, food_name: str, portion: float,
                   unit: str, calories: float, protein: float, carbs: float, fat: float) -> bool:
        return self._run(user_id, meal_type, food_name, portion, unit, calories, protein, carbs, fat)

class GetTodayMealsTool(BaseTool):
    """오늘의 식사 기록 조회 도구"""
    name: str = "GetTodayMealsTool"
    description: str = "오늘의 식사 기록을 조회하는 도구"
    
    def _run(self, user_id: int) -> List[Dict[str, Any]]:
        return api_client.get_today_meals(user_id)
        
    async def _arun(self, user_id: int) -> List[Dict[str, Any]]:
        return self._run(user_id)

class GetWeeklyMealsTool(BaseTool):
    """주간 식사 기록 조회 도구"""
    name: str = "GetWeeklyMealsTool"
    description: str = "주간 식사 기록을 조회하는 도구"
    
    def _run(self, user_id: int) -> List[Dict[str, Any]]:
        return api_client.get_weekly_meals(user_id)
        
    async def _arun(self, user_id: int) -> List[Dict[str, Any]]:
        return self._run(user_id)

class GetDietPlanTool(BaseTool):
    """식단 계획 조회 도구"""
    name: str = "GetDietPlanTool"
    description: str = "식단 계획을 조회하는 도구"
    
    def _run(self, diet_type: str, user_gender: str) -> Dict[str, Any]:
        return api_client.get_diet_plan(diet_type, user_gender)
        
    async def _arun(self, diet_type: str, user_gender: str) -> Dict[str, Any]:
        return self._run(diet_type, user_gender)

class GetUserPreferencesTool(BaseTool):
    """사용자 선호도 조회 도구"""
    name: str = "GetUserPreferencesTool"
    description: str = "사용자의 선호도를 조회하는 도구"
    
    def _run(self, user_id: int) -> Dict[str, Any]:
        return api_client.get_user_preferences(user_id)
        
    async def _arun(self, user_id: int) -> Dict[str, Any]:
        return self._run(user_id)

class AnalyzeWeeklyNutritionTool(BaseTool):
    """주간 영양소 분석 도구"""
    name: str = "AnalyzeWeeklyNutritionTool"
    description: str = "주간 영양소를 분석하는 도구"
    
    def _run(self, weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        
    async def _arun(self, weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._run(weekly_meals)

class RecommendFoodsTool(BaseTool):
    """음식 추천 도구"""
    name: str = "RecommendFoodsTool"
    description: str = "사용자에게 맞는 음식을 추천하는 도구"
    
    def _run(self, user_id: int) -> Dict[str, Any]:
        return api_client.recommend_foods(user_id)
        
    async def _arun(self, user_id: int) -> Dict[str, Any]:
        return self._run(user_id)

# 도구 인스턴스 생성
food_search_tool = FoodSearchTool()
user_info_tool = UserInfoTool()
food_nutrition_tool = FoodNutritionTool()
save_meal_record_tool = SaveMealRecordTool()
get_today_meals_tool = GetTodayMealsTool()
get_weekly_meals_tool = GetWeeklyMealsTool()
get_diet_plan_tool = GetDietPlanTool()
get_user_preferences_tool = GetUserPreferencesTool()
analyze_weekly_nutrition_tool = AnalyzeWeeklyNutritionTool()
recommend_foods_tool = RecommendFoodsTool()

# 도구 목록 생성
tools = [
    food_search_tool,
    user_info_tool,
    food_nutrition_tool,
    save_meal_record_tool,
    get_today_meals_tool,
    get_weekly_meals_tool,
    get_diet_plan_tool,
    get_user_preferences_tool,
    analyze_weekly_nutrition_tool,
    recommend_foods_tool
]

# LLM 초기화
llm = ChatOpenAI(temperature=0)

# 에이전트 초기화
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True
)

# 에이전트 실행
response = agent.run("사용자 ID 1의 오늘 식사 기록을 보여줘")


 
