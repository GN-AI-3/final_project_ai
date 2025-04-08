from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from agents.food.common.base_agent import BaseAgent
from agents.food.common.state import AgentState
from agents.food.common.db import (
    get_user_info, get_user_preferences_db, get_weekly_meals,
    analyze_weekly_nutrition, get_diet_plan, recommend_foods
)
import json
from datetime import datetime

class BalancedMealAgent(BaseAgent):
    """균형 잡힌 식사 추천 에이전트"""
    
    def __init__(self, model_name: str = BaseAgent.DEFAULT_MODEL):
        """에이전트 초기화"""
        super().__init__(model_name)
        self.prompts = self._initialize_prompts()
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "goal_conversion": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 사용자의 목표를 분석하여 가장 적합한 식단 유형을 선택해주세요.
                다음 중 하나를 선택해주세요:
                - 다이어트 식단
                - 벌크업 식단
                - 체력 증진 식단
                - 유지/균형 식단
                - 고단백/저탄수화물 식단
                
                사용자 목표: "{goal}"
                사용자 정보: {user_info}
                
                JSON 형식으로 응답해주세요:
                {{"diet_type": "선택된 식단 유형"}}
                """)
            ]),
            "meal_recommendation": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 사용자에게 맞는 식단을 추천해주세요.
                
                사용자 정보: {user_info}
                사용자 선호도: {preferences}
                식단 유형: {diet_type}
                주간 영양소 분석: {nutrition_analysis}
                
                JSON 형식으로 응답해주세요:
                {{"recommendations": [
                    {{"meal_type": "아침/점심/저녁/간식", "foods": ["음식1", "음식2", ...], "nutrition": {{"calories": 100, "protein": 10, "carbs": 20, "fat": 5}}}},
                    ...
                ]}}
                """)
            ])
        }
    
    @Tool
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 정보 조회"""
        return get_user_info(user_id)
    
    @Tool
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        return get_user_preferences_db(user_id)
    
    @Tool
    def get_weekly_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """주간 식사 기록 조회"""
        return get_weekly_meals(user_id)
    
    @Tool
    def analyze_weekly_nutrition(self, weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """주간 영양소 분석"""
        return analyze_weekly_nutrition(weekly_meals)
    
    @Tool
    def get_diet_plan(self, diet_type: str, user_gender: str) -> Optional[Dict[str, Any]]:
        """식단 계획 조회"""
        return get_diet_plan(diet_type, user_gender)
    
    @Tool
    def recommend_foods(self, user_id: int) -> Dict[str, Any]:
        """음식 추천"""
        return recommend_foods(user_id)
    
    async def get_user_data(self, state: AgentState) -> AgentState:
        """사용자 데이터 조회"""
        # 사용자 정보 조회
        user_info = await self.llm.ainvoke(f"사용자 ID {state.user_id}의 정보를 조회해주세요.")
        state.user_info = user_info
        
        # 사용자 선호도 조회
        preferences = await self.llm.ainvoke(f"사용자 ID {state.user_id}의 선호도를 조회해주세요.")
        state.user_preferences = preferences
        
        # 주간 식사 기록 조회
        weekly_meals = await self.llm.ainvoke(f"사용자 ID {state.user_id}의 주간 식사 기록을 조회해주세요.")
        state.weekly_meals = weekly_meals
        
        # 주간 영양소 분석
        nutrition_analysis = await self.llm.ainvoke(f"주간 식사 기록을 분석해주세요.")
        state.nutrition_analysis = nutrition_analysis
        
        state.next_step = "convert_goal"
        return state
    
    async def convert_goal(self, state: AgentState) -> AgentState:
        """목표를 식단 유형으로 변환"""
        if not state.user_info:
            state.error = "사용자 정보가 없습니다."
            state.next_step = "end"
            return state
        
        goal = state.user_info.get("goal", "")
        user_info = {
            "gender": state.user_info.get("gender", ""),
            "age": state.user_info.get("age", 0),
            "height": state.user_info.get("height", 0),
            "weight": state.user_info.get("weight", 0),
            "activity_level": state.user_info.get("activity_level", "")
        }
        
        prompt = self.prompts["goal_conversion"].format(
            goal=goal,
            user_info=json.dumps(user_info, ensure_ascii=False)
        )
        
        response = await self.llm.ainvoke(prompt)
        result = json.loads(response.content)
        
        state.diet_plan = result.get("diet_type", "")
        state.next_step = "get_diet_plan"
        
        return state
    
    async def get_diet_plan(self, state: AgentState) -> AgentState:
        """식단 계획 조회"""
        if not state.diet_plan or not state.user_info:
            state.error = "식단 유형 또는 사용자 정보가 없습니다."
            state.next_step = "end"
            return state
        
        diet_type = state.diet_plan
        gender = state.user_info.get("gender", "")
        
        diet_plan = await self.llm.ainvoke(f"식단 유형 '{diet_type}'과 성별 '{gender}'에 맞는 식단 계획을 조회해주세요.")
        state.diet_plan = diet_plan
        
        state.next_step = "recommend_meals"
        return state
    
    async def recommend_meals(self, state: AgentState) -> AgentState:
        """식사 추천"""
        if not state.user_info or not state.user_preferences or not state.diet_plan or not state.nutrition_analysis:
            state.error = "추천에 필요한 정보가 부족합니다."
            state.next_step = "end"
            return state
        
        prompt = self.prompts["meal_recommendation"].format(
            user_info=json.dumps(state.user_info, ensure_ascii=False),
            preferences=json.dumps(state.user_preferences, ensure_ascii=False),
            diet_type=state.diet_plan,
            nutrition_analysis=json.dumps(state.nutrition_analysis, ensure_ascii=False)
        )
        
        response = await self.llm.ainvoke(prompt)
        result = json.loads(response.content)
        
        state.food_recommendations = result.get("recommendations", [])
        state.next_step = "end"
        
        return state
    
    async def process(self, state: AgentState) -> AgentState:
        """식사 추천 처리"""
        # 워크플로우 실행
        if state.next_step == "get_user_data" or not state.next_step:
            state = await self.get_user_data(state)
        
        if state.next_step == "convert_goal":
            state = await self.convert_goal(state)
        
        if state.next_step == "get_diet_plan":
            state = await self.get_diet_plan(state)
        
        if state.next_step == "recommend_meals":
            state = await self.recommend_meals(state)
        
        return state 