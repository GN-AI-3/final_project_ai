from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from agents.food.common.base_agent import BaseAgent
from agents.food.common.state import AgentState
from agents.food.common.db import (
    save_meal_record, get_today_meals, get_weekly_meals, 
    get_food_nutrition, analyze_weekly_nutrition
)
import json
from datetime import datetime

class MealInputAgent(BaseAgent):
    """식사 입력 에이전트"""
    
    DEFAULT_PORTION_SIZE = 100  # 기본 1인분 크기 (그램)
    
    def __init__(self, model_name: str = BaseAgent.DEFAULT_MODEL):
        """에이전트 초기화"""
        super().__init__(model_name)
        self.prompts = self._initialize_prompts()
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "analyze_meal": ChatPromptTemplate.from_messages([
                ("system", """당신은 영양 전문가입니다. 사용자의 식사 입력을 분석하고 영양 정보를 제공해주세요.

다음 형식의 JSON으로만 응답하세요 (다른 텍스트 없이):
{"meal_items":[{"name":"음식 이름","portion":1,"unit":"개","calories":100,"protein":1,"carbs":25,"fat":0}],"total_nutrition":{"calories":100,"protein":1,"carbs":25,"fat":0}}

사용자 입력: "{user_input}"
""")
            ])
        }
    
    @Tool
    def get_food_nutrition(self, food_name: str) -> Optional[Dict[str, Any]]:
        """식품 영양소 정보 조회"""
        return get_food_nutrition(food_name)
    
    @Tool
    def save_meal_record(
        self,
        user_id: int,
        meal_type: str,
        food_name: str,
        portion: float,
        unit: str,
        calories: float,
        protein: float,
        carbs: float,
        fat: float
    ) -> bool:
        """식사 기록 저장"""
        return save_meal_record(
            user_id, meal_type, food_name, portion, unit,
            calories, protein, carbs, fat
        )
    
    @Tool
    def get_today_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """오늘의 식사 기록 조회"""
        return get_today_meals(user_id)
    
    @Tool
    def get_weekly_meals(self, user_id: int) -> List[Dict[str, Any]]:
        """주간 식사 기록 조회"""
        return get_weekly_meals(user_id)
    
    @Tool
    def analyze_weekly_nutrition(self, weekly_meals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """주간 영양소 분석"""
        return analyze_weekly_nutrition(weekly_meals)
    
    async def analyze_meal(self, state: AgentState) -> AgentState:
        """식사 입력 분석"""
        prompt = self.prompts["analyze_meal"].format(
            user_input=state.food_input
        )
        
        response = await self.llm.ainvoke(prompt)
        meal_data = self._parse_meal_data(response.content)
        
        if meal_data:
            state.meal_items = meal_data.get("meal_items", [])
            state.total_nutrition = meal_data.get("total_nutrition", {})
            state.next_step = "save_meal"
        else:
            state.error = "식사 입력을 분석할 수 없습니다."
            state.next_step = "end"
        
        return state
    
    async def save_meal(self, state: AgentState) -> AgentState:
        """식사 기록 저장"""
        if not state.meal_items:
            state.error = "저장할 식사 항목이 없습니다."
            state.next_step = "end"
            return state
        
        for item in state.meal_items:
            success = await self.llm.ainvoke(
                f"사용자 ID {state.user_id}의 식사 기록을 저장해주세요. "
                f"식사 유형: {state.meal_type}, "
                f"음식: {item['name']}, "
                f"양: {item['portion']} {item['unit']}, "
                f"칼로리: {item['calories']}, "
                f"단백질: {item['protein']}, "
                f"탄수화물: {item['carbs']}, "
                f"지방: {item['fat']}"
            )
            
            if not success:
                state.error = f"{item['name']} 저장 중 오류가 발생했습니다."
                state.next_step = "end"
                return state
        
        state.next_step = "analyze_nutrition"
        return state
    
    async def analyze_nutrition(self, state: AgentState) -> AgentState:
        """영양소 분석"""
        # 주간 식사 기록 조회
        weekly_meals = await self.llm.ainvoke(f"사용자 ID {state.user_id}의 주간 식사 기록을 조회해주세요.")
        state.weekly_meals = weekly_meals
        
        # 영양소 분석
        analysis = await self.llm.ainvoke(f"주간 식사 기록을 분석해주세요.")
        state.nutrition_analysis = analysis
        
        state.next_step = "end"
        return state
    
    def _parse_meal_data(self, response_content: str) -> Optional[Dict[str, Any]]:
        """식사 데이터 파싱"""
        try:
            # JSON 형식 확인
            if not response_content.strip().startswith('{'):
                return None
            
            # JSON 파싱
            data = json.loads(response_content)
            
            # 필수 필드 확인
            if "meal_items" not in data or "total_nutrition" not in data:
                return None
            
            return data
        except json.JSONDecodeError:
            return None
    
    async def process(self, state: AgentState) -> AgentState:
        """식사 입력 처리"""
        # 초기 상태 설정
        if not state.food_input:
            state.error = "식사 입력이 없습니다."
            return state
        
        # 워크플로우 실행
        if state.next_step == "analyze_meal" or not state.next_step:
            state = await self.analyze_meal(state)
        
        if state.next_step == "save_meal":
            state = await self.save_meal(state)
        
        if state.next_step == "analyze_nutrition":
            state = await self.analyze_nutrition(state)
        
        return state 