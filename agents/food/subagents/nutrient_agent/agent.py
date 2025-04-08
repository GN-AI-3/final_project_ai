from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from agents.food.common.base_agent import BaseAgent
from agents.food.common.state import AgentState
from agents.food.common.db import (
    get_weekly_meals, analyze_weekly_nutrition, recommend_foods
)
import json
from datetime import datetime

class NutrientAgent(BaseAgent):
    """영양소 분석 에이전트"""
    
    def __init__(self, model_name: str = BaseAgent.DEFAULT_MODEL):
        """에이전트 초기화"""
        super().__init__(model_name)
        self.prompts = self._initialize_prompts()
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "analyze_nutrition": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 주간 식사 기록을 분석하여 영양소 균형을 평가해주세요.
                
                주간 식사 기록: {weekly_meals}
                주간 영양소 분석: {nutrition_analysis}
                
                JSON 형식으로 응답해주세요:
                {{"analysis": {{
                    "overall_balance": "좋음/보통/나쁨",
                    "deficient_nutrients": ["부족한 영양소1", "부족한 영양소2", ...],
                    "excess_nutrients": ["과다한 영양소1", "과다한 영양소2", ...],
                    "recommendations": ["권장사항1", "권장사항2", ...]
                }}}}
                """)
            ]),
            "recommend_foods": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 부족한 영양소를 보완할 수 있는 음식을 추천해주세요.
                
                부족한 영양소: {deficient_nutrients}
                사용자 선호도: {preferences}
                
                JSON 형식으로 응답해주세요:
                {{"recommendations": [
                    {{"nutrient": "영양소명", "foods": ["음식1", "음식2", ...], "benefits": ["효과1", "효과2", ...]}},
                    ...
                ]}}
                """)
            ])
        }
    
    @Tool
    def get_weekly_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """주간 식사 기록 조회"""
        return get_weekly_meals(user_id)
    
    @Tool
    def analyze_weekly_nutrition(self, weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """주간 영양소 분석"""
        return analyze_weekly_nutrition(weekly_meals)
    
    @Tool
    def recommend_foods(self, user_id: int) -> Dict[str, Any]:
        """음식 추천"""
        return recommend_foods(user_id)
    
    async def get_weekly_data(self, state: AgentState) -> AgentState:
        """주간 데이터 조회"""
        # 주간 식사 기록 조회
        weekly_meals = await self.llm.ainvoke(f"사용자 ID {state.user_id}의 주간 식사 기록을 조회해주세요.")
        state.weekly_meals = weekly_meals
        
        # 주간 영양소 분석
        nutrition_analysis = await self.llm.ainvoke(f"주간 식사 기록을 분석해주세요.")
        state.nutrition_analysis = nutrition_analysis
        
        state.next_step = "analyze_nutrition"
        return state
    
    async def analyze_nutrition(self, state: AgentState) -> AgentState:
        """영양소 분석"""
        if not state.weekly_meals or not state.nutrition_analysis:
            state.error = "주간 데이터가 없습니다."
            state.next_step = "end"
            return state
        
        prompt = self.prompts["analyze_nutrition"].format(
            weekly_meals=json.dumps(state.weekly_meals, ensure_ascii=False),
            nutrition_analysis=json.dumps(state.nutrition_analysis, ensure_ascii=False)
        )
        
        response = await self.llm.ainvoke(prompt)
        result = json.loads(response.content)
        
        state.nutrition_analysis_result = result.get("analysis", {})
        state.next_step = "recommend_foods"
        
        return state
    
    async def recommend_foods_for_nutrients(self, state: AgentState) -> AgentState:
        """영양소 보완을 위한 음식 추천"""
        if not state.nutrition_analysis_result:
            state.error = "영양소 분석 결과가 없습니다."
            state.next_step = "end"
            return state
        
        deficient_nutrients = state.nutrition_analysis_result.get("deficient_nutrients", [])
        if not deficient_nutrients:
            state.food_recommendations = []
            state.next_step = "end"
            return state
        
        prompt = self.prompts["recommend_foods"].format(
            deficient_nutrients=json.dumps(deficient_nutrients, ensure_ascii=False),
            preferences=json.dumps(state.user_preferences, ensure_ascii=False) if state.user_preferences else "{}"
        )
        
        response = await self.llm.ainvoke(prompt)
        result = json.loads(response.content)
        
        state.food_recommendations = result.get("recommendations", [])
        state.next_step = "end"
        
        return state
    
    async def process(self, state: AgentState) -> AgentState:
        """영양소 분석 처리"""
        # 워크플로우 실행
        if state.next_step == "get_weekly_data" or not state.next_step:
            state = await self.get_weekly_data(state)
        
        if state.next_step == "analyze_nutrition":
            state = await self.analyze_nutrition(state)
        
        if state.next_step == "recommend_foods":
            state = await self.recommend_foods_for_nutrients(state)
        
        return state 