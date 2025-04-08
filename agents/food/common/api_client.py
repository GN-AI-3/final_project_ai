import os
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# API 기본 URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

class FoodAPIClient:
    """음식 관련 API 클라이언트"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 정보 조회"""
        response = requests.get(f"{self.base_url}/api/member/info/{user_id}")
        if response.status_code == 200:
            return response.json()
        return None
        
    def get_food_nutrition(self, food_name: str) -> Optional[Dict[str, Any]]:
        """식품 영양소 정보 조회"""
        response = requests.get(f"{self.base_url}/api/food/nutrition/{food_name}")
        if response.status_code == 200:
            return response.json()
        return None
        
    def save_meal_record(self, meal_data: Dict[str, Any]) -> bool:
        """식사 기록 저장"""
        response = requests.post(f"{self.base_url}/api/food/mealrecords/save", json=meal_data)
        return response.status_code == 200
        
    def get_today_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """오늘의 식사 기록 조회"""
        response = requests.get(f"{self.base_url}/api/food/mealrecords/today/{user_id}")
        if response.status_code == 200:
            return response.json()
        return []
        
    def get_weekly_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """주간 식사 기록 조회"""
        response = requests.get(f"{self.base_url}/api/food/mealrecords/weekly/{user_id}")
        if response.status_code == 200:
            return response.json()
        return []
        
    def get_diet_plan(self, diet_type: str, user_gender: str) -> Optional[Dict[str, Any]]:
        """식단 계획 조회"""
        response = requests.post(
            f"{self.base_url}/api/food/dietplans/plan",
            json={"dietType": diet_type, "userGender": user_gender}
        )
        if response.status_code == 200:
            return response.json()
        return None
        
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        response = requests.get(f"{self.base_url}/api/food/preferences/{user_id}")
        if response.status_code == 200:
            return response.json()
        return {}
        
    def recommend_foods(self, user_id: int) -> Dict[str, Any]:
        """음식 추천"""
        response = requests.get(f"{self.base_url}/api/food/recommend/{user_id}")
        if response.status_code == 200:
            return response.json()
        return {} 