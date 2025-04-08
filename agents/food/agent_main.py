from typing import Dict, Any, List, Optional, Tuple, Callable, Annotated
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain.schema import AIMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks.manager import CallbackManager
from langchain.tools import Tool
from agents.food.subagents.meal_input_agent.analyze import MealInputAgent
from agents.food.subagents.balanced_meal_agent.nodes import BalancedMealAgent
from agents.food.subagents.nutrient_agent.nodes import NutrientAgent
from agents.food.common.db import (
    get_user_info, get_food_nutrition, save_meal_record,
    get_today_meals, get_weekly_meals, get_diet_plan,
    get_user_preferences_db, recommend_foods, analyze_weekly_nutrition
)
from agents.food.common.tools import FoodSearchTool
from langgraph.graph import Graph, StateGraph, END
import json
import os
import inspect
from dataclasses import dataclass
from enum import Enum, auto
from agents.food.common.prompts import get_analyze_input_prompt
from agents.food.common.tools import get_user_schedule, add_reservation, modify_reservation
from langchain.schema import convert_to_openai_function
from agents.food.common.base_agent import BaseAgent
from agents.food.common.state import AgentState
from agents.food.workflow import MealNutrientWorkflow

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "food-agent"

class IntentType(Enum):
    """의도 타입"""
    MEAL_INPUT = auto()
    MEAL_RECOMMENDATION = auto()
    NUTRIENT_ANALYSIS = auto()
    MEAL_LOOKUP = auto()
    OTHER = auto()

@dataclass
class Intent:
    """의도 데이터 클래스"""
    type: IntentType
    confidence: float
    details: Dict[str, Any]

class FoodAgent(BaseAgent):
    """식사 관리 메인 에이전트"""
    
    def __init__(self, model_name: str = BaseAgent.DEFAULT_MODEL):
        """에이전트 초기화"""
        super().__init__(model_name)
        self.prompts = self._initialize_prompts()
        self._initialize_subagents()
        self._initialize_tools()
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "route_request": ChatPromptTemplate.from_messages([
                ("system", """당신은 식사 관리 시스템의 라우터입니다. 사용자의 요청을 분석하여 적절한 에이전트나 워크플로우로 연결해주세요.
                
                사용자 요청: {user_input}
                
                JSON 형식으로 응답해주세요:
                {{"route": "balanced_meal/meal_nutrient", "reason": "선택 이유"}}
                """)
            ])
        }
    
    def _initialize_subagents(self):
        """하위 에이전트 초기화"""
        self.balanced_meal_agent = BalancedMealAgent(self.model_name)
        self.meal_input_agent = MealInputAgent(self.model_name)
        self.nutrient_agent = NutrientAgent(self.model_name)
        self.meal_nutrient_workflow = MealNutrientWorkflow(
            meal_input_agent=self.meal_input_agent,
            nutrient_agent=self.nutrient_agent
        )
    
    def _initialize_tools(self):
        """도구 초기화"""
        self.functions = []
        for attr in dir(self):
            fn = getattr(self, attr)
            if hasattr(fn, "_langchain_tool"):
                self.functions.append(fn)
        
        # LLM에 도구 바인딩
        self.llm = self.llm.bind_tools(self.functions)
    
    @Tool
    def route_request(self, user_input: str) -> Dict[str, str]:
        """사용자 요청을 적절한 에이전트/워크플로우로 라우팅"""
        prompt = self.prompts["route_request"].format(user_input=user_input)
        response = self.llm.invoke(prompt)
        return json.loads(response.content)
    
    async def run(self, user_input: str, state: AgentState) -> AgentState:
        """에이전트 실행"""
        # 요청 라우팅
        route = await self.route_request(user_input)
        state.route = route["route"]
        
        # 라우팅에 따라 적절한 에이전트/워크플로우 실행
        if route["route"] == "balanced_meal":
            return await self.balanced_meal_agent.process(state)
        elif route["route"] == "meal_nutrient":
            return await self.meal_nutrient_workflow.run(state)
        else:
            state.error = f"알 수 없는 라우트: {route['route']}"
            return state
 