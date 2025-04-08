from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from agents.food.common.tools import (
    get_user_info,
    get_food_nutrition,
    save_meal_record,
    get_today_meals,
    get_weekly_meals,
    get_diet_plan,
    get_user_preferences_db,
    recommend_foods
)
import json
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class UserState(BaseModel):
    """사용자 상태"""
    model_config = ConfigDict(validate_by_name=True)
    user_data: Dict[str, Any] = Field(default_factory=dict)
    food_info: Dict[str, Any] = Field(default_factory=dict)
    bmi: float = 0.0
    bmi_status: str = ""
    nutrition_analysis: Dict[str, Any] = Field(default_factory=dict)
    supplement_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    meal_plan: str = ""
    confidence: float = 0.0

def vector_search_node(state: UserState) -> UserState:
    """벡터 검색 노드"""
    # 벡터 검색 로직 구현
    # 예시 구현
    state.confidence = 0.9
    return state

def evaluate_data_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """데이터 평가 노드"""
    # 데이터 평가 로직 구현
    # 예시 구현
    state.confidence = 0.85
    return state

def self_rag_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """자체 RAG 노드"""
    # 자체 RAG 로직 구현
    # 예시 구현
    state.confidence = 0.9
    return state

def bmi_calculation_node(state: UserState) -> UserState:
    """BMI 계산 노드"""
    # 사용자 정보 가져오기
    user_id = state.user_data.get("user_id", 1)  # 기본값 1
    user_info = get_user_info(user_id)
    
    # BMI 계산
    if "height" in user_info and "weight" in user_info:
        height_m = user_info["height"] / 100
        weight_kg = user_info["weight"]
        bmi = weight_kg / (height_m * height_m)
        state.bmi = bmi
        
        if bmi < 18.5:
            state.bmi_status = "저체중"
        elif bmi < 25:
            state.bmi_status = "정상"
        elif bmi < 30:
            state.bmi_status = "과체중"
        else:
            state.bmi_status = "비만"
    
    return state

def nutrition_calculation_node(state: UserState) -> UserState:
    """영양 계산 노드"""
    # 사용자 정보 가져오기
    user_id = state.user_data.get("user_id", 1)  # 기본값 1
    
    # 주간 식사 기록 가져오기
    weekly_meals = get_weekly_meals(user_id)
    
    # 영양 정보 계산
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    for meal in weekly_meals:
        food_name = meal.get("food_name", "")
        if food_name:
            food_nutrition = get_food_nutrition(food_name)
            total_calories += food_nutrition.get("calories", 0)
            total_protein += food_nutrition.get("protein", 0)
            total_carbs += food_nutrition.get("carbs", 0)
            total_fat += food_nutrition.get("fat", 0)
    
    # 상태 업데이트
    state.food_info = {
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat
    }
    
    return state

def nutrition_analysis_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """영양 분석 노드"""
    # 사용자 정보 가져오기
    user_id = state.user_data.get("user_id", 1)  # 기본값 1
    
    # 사용자 선호도 가져오기
    user_preferences = get_user_preferences_db(user_id)
    
    # 식단 계획 가져오기
    diet_plan = get_diet_plan(user_id)
    
    # 영양 분석 결과
    state.nutrition_analysis = {
        "evaluation": "균형 잡힌 식단입니다.",
        "deficient_nutrients": ["비타민 D", "칼슘"]
    }
    
    return state

def recommend_supplements_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """보충제 추천 노드"""
    # 사용자 정보 가져오기
    user_id = state.user_data.get("user_id", 1)  # 기본값 1
    
    # 식품 추천 가져오기
    food_recommendations = recommend_foods(user_id)
    
    # 보충제 추천 결과
    state.supplement_recommendations = [
        {
            "name": "비타민 D 보충제",
            "reason": "비타민 D가 부족합니다."
        },
        {
            "name": "칼슘 보충제",
            "reason": "칼슘이 부족합니다."
        }
    ]
    
    return state

def meal_planning_node(state: UserState, llm: ChatOpenAI) -> UserState:
    """식사 계획 노드"""
    # 사용자 정보 가져오기
    user_id = state.user_data.get("user_id", 1)  # 기본값 1
    
    # 사용자 선호도 가져오기
    user_preferences = get_user_preferences_db(user_id)
    
    # 식단 계획 가져오기
    diet_plan = get_diet_plan(user_id)
    
    # 식사 계획 결과
    state.meal_plan = """
    아침: 오트밀, 바나나, 견과류
    점심: 닭가슴살 샐러드, 현미밥
    저녁: 연어, 브로콜리, 고구마
    간식: 요거트, 블루베리
    """
    
    return state 