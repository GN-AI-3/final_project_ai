from typing import Dict, Any, List
from tavily import TavilyClient
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
from langchain.tools import Tool, tool
from agents.food.common.db import (
    get_user_info as db_get_user_info,
    get_food_nutrition as db_get_food_nutrition,
    save_meal_record as db_save_meal_record,
    get_today_meals as db_get_today_meals,
    get_weekly_meals as db_get_weekly_meals,
    get_diet_plan as db_get_diet_plan,
    get_user_preferences_db as db_get_user_preferences_db,
    recommend_foods as db_recommend_foods
)

load_dotenv()

@tool
async def get_user_info(user_id: int) -> Dict[str, Any]:
    """사용자 정보를 조회합니다."""
    # 데이터베이스에서 사용자 정보 조회
    user_info = db_get_user_info(user_id)
    if user_info:
        return user_info
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return {"user_id": user_id, "weight": 70, "activity_level": "보통"}

@tool
async def get_food_nutrition(food_name: str) -> Dict[str, Any]:
    """음식의 영양 정보를 조회합니다."""
    # 데이터베이스에서 음식 영양 정보 조회
    food_nutrition = db_get_food_nutrition(food_name)
    if food_nutrition:
        return food_nutrition
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return {"name": food_name, "calories": 100, "protein": 10, "carbs": 20, "fat": 5}

@tool
async def save_meal_record(user_id: int, meal_data: Dict[str, Any]) -> bool:
    """식사 기록을 저장합니다."""
    # 데이터베이스에 식사 기록 저장
    try:
        return db_save_meal_record(
            user_id=user_id,
            meal_type=meal_data.get("meal_type", "기타"),
            food_name=meal_data.get("food_name", ""),
            portion=meal_data.get("portion", 1.0),
            unit=meal_data.get("unit", "개"),
            calories=meal_data.get("calories", 0.0),
            protein=meal_data.get("protein", 0.0),
            carbs=meal_data.get("carbs", 0.0),
            fat=meal_data.get("fat", 0.0)
        )
    except Exception as e:
        print(f"식사 기록 저장 중 오류 발생: {e}")
        return False

@tool
async def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    """오늘의 식사 기록을 조회합니다."""
    # 데이터베이스에서 오늘의 식사 기록 조회
    today_meals = db_get_today_meals(user_id)
    if today_meals:
        return today_meals
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return [{"meal_type": "아침", "food_name": "계란", "calories": 70}]

@tool
async def get_weekly_meals(user_id: int) -> List[Dict[str, Any]]:
    """주간 식사 기록을 조회합니다."""
    # 데이터베이스에서 주간 식사 기록 조회
    weekly_meals = db_get_weekly_meals(user_id)
    if weekly_meals:
        return weekly_meals
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return [{"meal_type": "아침", "food_name": "계란", "calories": 70}]

@tool
async def get_diet_plan(user_id: int) -> Dict[str, Any]:
    """식단 계획을 조회합니다."""
    # 사용자 정보 조회
    user_info = db_get_user_info(user_id)
    if not user_info:
        return {"plan": "균형 잡힌 식단"}
    
    # 데이터베이스에서 식단 계획 조회
    diet_plan = db_get_diet_plan(
        diet_type="균형 잡힌 식단",
        user_gender=user_info.get("gender", "남성")
    )
    if diet_plan:
        return diet_plan
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return {"plan": "균형 잡힌 식단"}

@tool
async def get_user_preferences_db(user_id: int) -> Dict[str, Any]:
    """사용자의 식품 선호도를 조회합니다."""
    # 데이터베이스에서 사용자 선호도 조회
    user_preferences = db_get_user_preferences_db(user_id)
    if user_preferences:
        return user_preferences
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return {"preferred_ingredients": ["계란", "현미"]}

@tool
async def recommend_foods(user_id: int) -> Dict[str, Any]:
    """사용자의 식사 기록을 분석하여 식품을 추천합니다."""
    # 데이터베이스에서 식품 추천 조회
    food_recommendations = db_recommend_foods(user_id)
    if food_recommendations:
        return food_recommendations
    # 데이터베이스에서 정보를 가져오지 못한 경우 기본값 반환
    return {
        "recommended_foods": [
            {"type": "protein", "foods": [{"name": "계란", "calories": 70, "protein": 6, "carbs": 0, "fat": 5, "portion": 1, "unit": "개"}]},
            {"type": "carbs", "foods": [{"name": "현미", "calories": 216, "protein": 5, "carbs": 45, "fat": 1.8, "portion": 100, "unit": "g"}]}
        ]
    }

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