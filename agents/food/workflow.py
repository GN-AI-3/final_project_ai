from typing import Dict, Any, List, Optional
from langchain.graphs import StateGraph
from langchain_openai import ChatOpenAI
from agents.food.nodes import UserState
from agents.food.common.tools import (
    get_user_info_tool,
    get_food_nutrition_tool,
    save_meal_record_tool,
    get_today_meals_tool,
    get_weekly_meals_tool,
    get_diet_plan_tool,
    get_user_preferences_tool,
    recommend_foods_tool
)

class MealNutrientWorkflow:
    """식사 입력과 영양 분석을 위한 워크플로우"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.graph = self._create_graph()
        
    def _create_graph(self) -> StateGraph:
        """워크플로우 그래프 생성"""
        workflow = StateGraph(UserState)
        
        # 노드 추가
        workflow.add_node("get_user_info", self._get_user_info)
        workflow.add_node("get_meal_records", self._get_meal_records)
        workflow.add_node("analyze_nutrition", self._analyze_nutrition)
        workflow.add_node("recommend_foods", self._recommend_foods)
        
        # 엣지 추가
        workflow.add_edge("get_user_info", "get_meal_records")
        workflow.add_edge("get_meal_records", "analyze_nutrition")
        workflow.add_edge("analyze_nutrition", "recommend_foods")
        
        # 시작 노드 설정
        workflow.set_entry_point("get_user_info")
        
        return workflow.compile()
    
    def _get_user_info(self, state: UserState) -> UserState:
        """사용자 정보 조회"""
        user_info = get_user_info_tool(state.user_id)
        state.user_info = user_info
        return state
    
    def _get_meal_records(self, state: UserState) -> UserState:
        """식사 기록 조회"""
        meal_records = get_weekly_meals_tool(state.user_id)
        state.meal_records = meal_records
        return state
    
    def _analyze_nutrition(self, state: UserState) -> UserState:
        """영양 분석"""
        # 영양 분석 로직 구현
        state.food_info = {
            "total_calories": 0,
            "total_protein": 0,
            "total_carbs": 0,
            "total_fat": 0
        }
        
        for meal in state.meal_records:
            food_name = meal.get("food_name", "")
            if food_name:
                food_nutrition = get_food_nutrition_tool(food_name)
                state.food_info["total_calories"] += food_nutrition.get("calories", 0)
                state.food_info["total_protein"] += food_nutrition.get("protein", 0)
                state.food_info["total_carbs"] += food_nutrition.get("carbs", 0)
                state.food_info["total_fat"] += food_nutrition.get("fat", 0)
        
        return state
    
    def _recommend_foods(self, state: UserState) -> UserState:
        """식품 추천"""
        recommended_foods = recommend_foods_tool(state.user_id)
        state.recommended_foods = recommended_foods
        return state
    
    def run(self, user_id: int) -> Dict[str, Any]:
        """워크플로우 실행"""
        initial_state = UserState(user_id=user_id)
        final_state = self.graph.invoke(initial_state)
        return final_state.dict()
