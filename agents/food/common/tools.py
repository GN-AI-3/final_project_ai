from typing import Dict, Any, List
from tavily import TavilyClient
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
from langchain.tools import Tool, tool
from agents.food.common.db import (
    get_user_info,
    get_food_nutrition,
    save_meal_record,
    get_today_meals,
    get_weekly_meals,
    get_diet_plan,
    get_user_preferences_db,
    recommend_foods
)

load_dotenv()

@tool
async def get_user_info_tool(user_id: int) -> Dict[str, Any]:
    """사용자 정보를 조회합니다."""
    return get_user_info(user_id)

@tool
async def get_food_nutrition_tool(food_name: str) -> Dict[str, Any]:
    """음식의 영양 정보를 조회합니다."""
    return get_food_nutrition(food_name)

@tool
async def save_meal_record_tool(user_id: int, meal_data: Dict[str, Any]) -> bool:
    """식사 기록을 저장합니다."""
    return save_meal_record(user_id, meal_data)

@tool
async def get_today_meals_tool(user_id: int) -> List[Dict[str, Any]]:
    """오늘의 식사 기록을 조회합니다."""
    return get_today_meals(user_id)

@tool
async def get_weekly_meals_tool(user_id: int) -> List[Dict[str, Any]]:
    """주간 식사 기록을 조회합니다."""
    return get_weekly_meals(user_id)

@tool
async def get_diet_plan_tool(diet_type: str, user_gender: str) -> Dict[str, Any]:
    """식단 계획을 조회합니다."""
    return get_diet_plan(diet_type, user_gender)

@tool
async def get_user_preferences_tool(user_id: int) -> Dict[str, Any]:
    """사용자 선호도를 조회합니다."""
    return get_user_preferences_db(user_id)

@tool
async def recommend_foods_tool(user_id: int, deficient_nutrients: List[str]) -> List[Dict[str, Any]]:
    """영양소 기반 음식을 추천합니다."""
    return recommend_foods(user_id, deficient_nutrients)

class FoodSearchTool(Tool):
    name = "FoodSearchTool"
    description = "Use this tool to search for food information"

    async def _run(self, query: str) -> str:
        # 검색 API를 사용하여 음식 정보를 검색
        search_tool = FoodSearchTool()
        result = await search_tool.search_food_info(query)
        return result

    @tool
    async def search_food_info(self, query: str) -> List[Dict[str, Any]]:
        """음식 정보 검색"""
        try:
            # 검색 API를 사용하여 음식 정보를 검색
            search_results = await self._search(query)
            return search_results
        except Exception as e:
            print(f"음식 정보 검색 중 오류 발생: {e}")
            return []

    async def _search(self, query: str) -> List[Dict[str, Any]]:
        """검색 API를 사용하여 음식 정보를 검색"""
        # 검색 API를 사용하여 음식 정보를 검색하는 로직
        # 예시: 검색 API를 사용하여 음식 정보를 검색
        return [
            {"name": "검색 결과 1", "calories": 100, "protein": 10, "carbs": 20, "fat": 5},
            {"name": "검색 결과 2", "calories": 200, "protein": 20, "carbs": 30, "fat": 10}
        ]

    def __init__(self):
        """초기화"""
        self.client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    async def search_food_info(self, query: str) -> Dict[str, Any]:
        """음식 정보 검색 및 영양 정보 추출"""
        try:
            # 검색 엔진 사용
            search_result = self.client.search(
                query=f"{query} 칼로리 단백질 탄수화물 지방 영양정보",
                search_depth="advanced",
                include_domains=["koreanfood.rda.go.kr", "foodnara.go.kr", "kfda.go.kr"],
                max_results=3
            )
            
            if search_result.get("results"):
                print(f"검색 결과: {search_result['results']}")  # 검색 결과 출력
                nutrition_info = await self._extract_nutrition_info(search_result["results"], query)
                if nutrition_info["calories"] > 0:
                    return nutrition_info
            
            # 검색 결과가 없는 경우 LLM이 판단
            print("LLM이 판단합니다.")  # LLM 판단 메시지 출력
            return self._create_default_nutrition_info(query)
            
        except Exception as e:
            print(f"음식 정보 검색 중 오류 발생: {e}")
            return self._create_default_nutrition_info(query)
    
    async def search_recipe(self, ingredients: List[str]) -> Dict[str, Any]:
        """레시피 검색 및 영양 정보 추출"""
        try:
            # 웹 검색 수행
            query = f"healthy recipe with {', '.join(ingredients)} nutrition facts"
            search_result = self.client.search(
                query=query,
                search_depth="advanced",
                include_domains=["fatsecret.com","allrecipes.com", "foodnetwork.com", "cookinglight.com","naver.com","google.com"],
                max_results=5
            )
            
            # 검색 결과가 없는 경우
            if not search_result.get("results"):
                return self._create_default_recipe_info(ingredients)
            
            # LLM을 사용하여 레시피 및 영양 정보 추출
            recipe_info = await self._extract_recipe_info(search_result["results"], ingredients)
            return recipe_info
            
        except Exception as e:
            print(f"레시피 검색 중 오류 발생: {e}")
            return self._create_default_recipe_info(ingredients)
    
    async def _extract_nutrition_info(self, search_results: List[Dict[str, Any]], food_name: str) -> Dict[str, Any]:
        """검색 결과에서 영양 정보 추출"""
        try:
            # 검색 결과를 텍스트로 변환
            search_text = "\n".join([result.get("content", "") for result in search_results])
            
            # LLM 프롬프트 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", """다음 검색 결과에서 음식의 영양 정보를 추출하여 JSON 형식으로 반환하세요.
                반드시 다음 필드를 포함해야 합니다:
                - name: 음식 이름
                - calories: 칼로리 (kcal)
                - protein: 단백질 (g)
                - carbs: 탄수화물 (g)
                - fat: 지방 (g)
                - portion: 1회 제공량
                - unit: 단위 (g, ml 등)
                
                주의사항:
                1. 모든 수치는 숫자로 변환하여 반환하세요.
                2. 단위가 다른 경우 g 또는 kcal로 변환하세요.
                3. 정보가 불확실한 경우 0을 반환하지 말고, 가장 가능성 높은 값을 추정하여 반환하세요.
                4. 한국 음식의 경우 일반적인 1인분 기준으로 변환하세요.
                """),
                ("human", f"음식 이름: {food_name}\n\n검색 결과:\n{search_text}")
            ])
            
            # LLM 호출
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            
            # JSON 파싱
            try:
                result = json.loads(response.content)
                
                # 수치 검증
                for key in ["calories", "protein", "carbs", "fat"]:
                    if key in result:
                        try:
                            result[key] = float(result[key])
                        except (ValueError, TypeError):
                            result[key] = 0.0
                
                return result
            except json.JSONDecodeError:
                return self._create_default_nutrition_info(food_name)
                
        except Exception as e:
            print(f"영양 정보 추출 중 오류 발생: {e}")
            return self._create_default_nutrition_info(food_name)
    
    async def _extract_recipe_info(self, search_results: List[Dict[str, Any]], ingredients: List[str]) -> Dict[str, Any]:
        """검색 결과에서 레시피 및 영양 정보 추출"""
        try:
            # 검색 결과를 텍스트로 변환
            search_text = "\n".join([result.get("content", "") for result in search_results])
            
            # LLM 프롬프트 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", """다음 검색 결과에서 레시피와 영양 정보를 추출하여 JSON 형식으로 반환하세요.
                반드시 다음 필드를 포함해야 합니다:
                - name: 레시피 이름
                - ingredients: 재료 목록
                - instructions: 조리 방법
                - nutrition: 영양 정보
                  - calories: 칼로리 (kcal)
                  - protein: 단백질 (g)
                  - carbs: 탄수화물 (g)
                  - fat: 지방 (g)
                - portion: 1회 제공량
                - unit: 단위 (인분, 그램 등)
                """),
                ("human", f"재료: {', '.join(ingredients)}\n\n검색 결과:\n{search_text}")
            ])
            
            # LLM 호출
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            
            # JSON 파싱
            try:
                result = json.loads(response.content)
                return result
            except json.JSONDecodeError:
                return self._create_default_recipe_info(ingredients)
                
        except Exception as e:
            print(f"레시피 정보 추출 중 오류 발생: {e}")
            return self._create_default_recipe_info(ingredients)
    
    def _create_default_nutrition_info(self, food_name: str) -> Dict[str, Any]:
        """기본 영양 정보 생성"""
        return {
            "name": food_name,
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "portion": 100,
            "unit": "g"
        }
    
    def _create_default_recipe_info(self, ingredients: List[str]) -> Dict[str, Any]:
        """기본 레시피 정보 생성"""
        return {
            "name": f"{', '.join(ingredients)} 레시피",
            "ingredients": ingredients,
            "instructions": "조리 방법을 찾을 수 없습니다.",
            "nutrition": {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0
            },
            "portion": 1,
            "unit": "인분"
        }

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