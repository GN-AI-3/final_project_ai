import pandas as pd
import numpy as np
from typing import Dict, List, Any
import json
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
import requests
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.font_manager as fm
  
@tool("search_food_info")
def search_food_info(food_name: str) -> Dict[str, Any]:
    """
    음식 정보를 검색하는 도구
    
    Args:
        food_name (str): 검색할 음식 이름
        
    Returns:
        Dict[str, Any]: 음식의 영양 정보
    """
    # 네이버 검색 API 사용
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    url = f"https://search.naver.com/search.naver?query={food_name}+영양성분"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        nutrition_info = {
            "name": food_name,
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0
        }
        
        # 영양 정보 파싱 로직
        nutrition_elements = soup.find_all("div", class_="nutrition_info")
        if nutrition_elements:
            for element in nutrition_elements:
                text = element.get_text()
                if "칼로리" in text:
                    nutrition_info["calories"] = float(text.split("칼로리")[0].strip())
                elif "단백질" in text:
                    nutrition_info["protein"] = float(text.split("단백질")[0].strip())
                elif "탄수화물" in text:
                    nutrition_info["carbs"] = float(text.split("탄수화물")[0].strip())
                elif "지방" in text:
                    nutrition_info["fat"] = float(text.split("지방")[0].strip())
        
        return nutrition_info
    except Exception as e:
        print(f"음식 정보 검색 중 오류 발생: {e}")
        return nutrition_info

@tool("calculate_bmr")
def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """
    기초대사량(BMR)을 계산하는 도구
    
    Args:
        weight (float): 체중(kg)
        height (float): 신장(cm)
        age (int): 나이
        gender (str): 성별 ('male' 또는 'female')
        
    Returns:
        float: 계산된 BMR
    """
    if gender.lower() == 'male':
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)
    return bmr

@tool("calculate_tdee")
def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    일일 총 에너지 소비량(TDEE)을 계산하는 도구
    
    Args:
        bmr (float): 기초대사량
        activity_level (str): 활동 수준
        
    Returns:
        float: 계산된 TDEE
    """
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    return bmr * activity_multipliers.get(activity_level, 1.2)

@tool("analyze_nutrition")
def analyze_nutrition(foods: List[Dict[str, Any]], target_calories: float) -> Dict[str, Any]:
    """
    식단의 영양소를 분석하는 도구
    
    Args:
        foods (List[Dict[str, Any]]): 식품 목록과 영양 정보
        target_calories (float): 목표 칼로리
        
    Returns:
        Dict[str, Any]: 영양 분석 결과
    """
    total_nutrition = {
        "calories": sum(food.get("calories", 0) for food in foods),
        "protein": sum(food.get("protein", 0) for food in foods),
        "carbs": sum(food.get("carbs", 0) for food in foods),
        "fat": sum(food.get("fat", 0) for food in foods)
    }
    
    analysis = {
        "total_nutrition": total_nutrition,
        "meets_target": abs(total_nutrition["calories"] - target_calories) <= 100,
        "deficient_nutrients": []
    }
    
    # 영양소 부족 분석
    if total_nutrition["protein"] < target_calories * 0.3 / 4:
        analysis["deficient_nutrients"].append("단백질")
    if total_nutrition["carbs"] < target_calories * 0.4 / 4:
        analysis["deficient_nutrients"].append("탄수화물")
    if total_nutrition["fat"] < target_calories * 0.3 / 9:
        analysis["deficient_nutrients"].append("지방")
    
    return analysis

@tool("generate_meal_plan")
def generate_meal_plan(
    target_calories: float,
    nutrition_analysis: Dict[str, Any],
    preferences: List[str]
) -> List[Dict[str, Any]]:
    """
    맞춤형 식단을 생성하는 도구
    
    Args:
        target_calories (float): 목표 칼로리
        nutrition_analysis (Dict[str, Any]): 영양 분석 결과
        preferences (List[str]): 선호하는 음식 목록
        
    Returns:
        List[Dict[str, Any]]: 생성된 식단
    """
    meal_plan = []
    meals = ["아침", "점심", "저녁"]
    calories_per_meal = target_calories / len(meals)
    
    for meal_type in meals:
        meal = {
            "meal_type": meal_type,
            "foods": [],
            "total_calories": 0
        }
        # 식단 생성 로직
        meal_plan.append(meal)
    
    return meal_plan 