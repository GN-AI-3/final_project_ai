from typing import Dict, Any, List
from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()

class FoodSearchTool:
    """음식 검색 도구"""
    
    def __init__(self):
        """초기화"""
        self.client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    async def search_food_info(self, query: str) -> List[Dict[str, Any]]:
        """음식 정보 검색"""
        try:
            search_result = self.client.search(
                query=query,
                search_depth="advanced",
                include_domains=["healthline.com", "webmd.com", "nutritionix.com"],
                max_results=5
            )
            return search_result.get("results", [])
        except Exception as e:
            print(f"음식 정보 검색 중 오류 발생: {e}")
            return []
    
    async def search_recipe(self, ingredients: List[str]) -> List[Dict[str, Any]]:
        """레시피 검색"""
        try:
            query = f"healthy recipe with {', '.join(ingredients)}"
            search_result = self.client.search(
                query=query,
                search_depth="advanced",
                include_domains=["allrecipes.com", "foodnetwork.com", "cookinglight.com"],
                max_results=5
            )
            return search_result.get("results", [])
        except Exception as e:
            print(f"레시피 검색 중 오류 발생: {e}")
            return []
    
    async def search_nutrition_tips(self, topic: str) -> List[Dict[str, Any]]:
        """영양 정보 팁 검색"""
        try:
            query = f"nutrition tips for {topic}"
            search_result = self.client.search(
                query=query,
                search_depth="advanced",
                include_domains=["healthline.com", "webmd.com", "mayoclinic.org"],
                max_results=5
            )
            return search_result.get("results", [])
        except Exception as e:
            print(f"영양 정보 팁 검색 중 오류 발생: {e}")
            return [] 