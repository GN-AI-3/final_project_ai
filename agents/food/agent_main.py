from typing import Dict, Any, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain.schema import AIMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks.manager import CallbackManager
from agents.food.subagents.meal_input_agent.analyze import MealInputAgent
from agents.food.subagents.balanced_meal_agent.nodes import BalancedMealAgent
from agents.food.subagents.nutrient_agent.nodes import NutrientAgent
from agents.food.common.db import (
    get_user_info, get_food_nutrition, save_meal_record,
    get_today_meals, get_weekly_meals, get_diet_plan,
    get_user_preferences_db, recommend_foods
)
from agents.food.common.tools import FoodSearchTool
from langgraph.graph import Graph, StateGraph
import json
import os
from dataclasses import dataclass
from enum import Enum, auto
from agents.food.common.prompts import get_analyze_input_prompt

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

class FoodAgent:
    """음식 관련 에이전트"""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """음식 에이전트 초기화"""
        self.model_name = self._validate_model_name(model_name)
        self.llm = self._initialize_llm()
        self.prompts = self._initialize_prompts()
        self.subagents = self._initialize_subagents()
        self.search_tool = FoodSearchTool()
    
    def _validate_model_name(self, model_name: str) -> str:
        """모델 이름 유효성 검사"""
        return model_name if model_name and isinstance(model_name, str) else self.DEFAULT_MODEL
    
    def _initialize_llm(self) -> ChatOpenAI:
        """LLM 초기화"""
        return ChatOpenAI(
            model=self.model_name,
            temperature=0.7
        )
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """프롬프트 초기화"""
        return {
            "intent": ChatPromptTemplate.from_messages([
                ("system", """사용자의 의도를 분석하는 AI 어시스턴트입니다.
                다음 형식의 JSON으로 응답해주세요:
                {{
                    "intent": "MEAL_INPUT/MEAL_RECOMMENDATION/NUTRIENT_ANALYSIS/MEAL_LOOKUP/OTHER",
                    "confidence": 0.0-1.0,
                    "details": {{
                        "meal_type": "아침/점심/저녁/간식",
                        "foods": ["음식1", "음식2", ...]
                    }}
                }}"""),
                ("human", "{input}")
            ])
        }
    
    def _initialize_subagents(self) -> Dict[str, Any]:
        """하위 에이전트 초기화"""
        return {
            IntentType.MEAL_INPUT: MealInputAgent(self.model_name),
            IntentType.MEAL_RECOMMENDATION: BalancedMealAgent(self.model_name),
            IntentType.NUTRIENT_ANALYSIS: NutrientAgent(self.model_name),
            IntentType.MEAL_LOOKUP: BalancedMealAgent(self.model_name),
            IntentType.OTHER: BalancedMealAgent(self.model_name)
        }
    
    def _parse_intent(self, response: AIMessage) -> Optional[Intent]:
        """의도 파싱"""
        try:
            data = json.loads(response.content)
            return Intent(
                type=IntentType[data["intent"]],
                confidence=float(data["confidence"]),
                details=data.get("details", {})
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    async def _analyze_intent(self, user_input: str) -> Optional[Intent]:
        """사용자 의도 분석"""
        chain = self.prompts["intent"] | self.llm
        response = await chain.ainvoke({"input": user_input})
        
        if not isinstance(response, AIMessage):
            return None
        
        return self._parse_intent(response)
    
    def _get_subagent(self, intent_type: IntentType) -> Optional[Any]:
        """하위 에이전트 조회"""
        return self.subagents.get(intent_type)
    
    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "type": "food",
            "response": f"죄송합니다. {message}"
        }
    
    async def process(self, user_input: str, user_id: str = "1") -> Dict[str, Any]:
        """사용자 입력 처리"""
        try:
            # LLM을 사용하여 의도 분석
            intent_analysis = await self._analyze_intent_with_llm(user_input)
            print(f"의도 분석 결과: {intent_analysis}")  # 디버깅용 로그 추가
            
            # 식사 타입 추출
            meal_type = intent_analysis.get("meal_time", "간식")
            
            # 의도에 따른 처리
            if intent_analysis["intent"] == "식사 기록":
                # 식사 입력 처리
                meal_input_agent = self._get_subagent(IntentType.MEAL_INPUT)
                if meal_input_agent:
                    # 웹 검색으로 음식 정보 보완
                    food_name = intent_analysis.get("food_name", "")
                    if food_name:
                        food_info = await self.search_tool.search_food_info(food_name)
                        if food_info:
                            # 검색 결과를 포함하여 처리
                            return await meal_input_agent.process(
                                user_input=user_input,
                                user_id=user_id,
                                meal_type=meal_type,
                                food_info=food_info
                            )
                    
                    return await meal_input_agent.process(
                        user_input=user_input,
                        user_id=user_id,
                        meal_type=meal_type
                    )
                else:
                    return self._create_error_response("식사 입력 처리를 위한 에이전트를 찾을 수 없습니다.")
            elif intent_analysis["intent"] == "식단 추천":
                # 식단 추천 처리
                meal_recommendation_agent = self._get_subagent(IntentType.MEAL_RECOMMENDATION)
                if meal_recommendation_agent:
                    # 웹 검색으로 식단 정보 보완
                    food_preferences = await get_user_preferences_db(int(user_id))
                    if food_preferences:
                        ingredients = food_preferences.get("preferred_ingredients", [])
                        if ingredients:
                            recipe_info = await self.search_tool.search_recipe(ingredients)
                            if recipe_info:
                                # 검색 결과를 포함하여 처리
                                return await meal_recommendation_agent.process(
                                    user_input=user_input,
                                    user_id=user_id,
                                    recipe_info=recipe_info
                                )
                    
                    return await meal_recommendation_agent.process(
                        user_input=user_input,
                        user_id=user_id
                    )
                else:
                    return self._create_error_response("식단 추천을 위한 에이전트를 찾을 수 없습니다.")
            else:
                return self._create_error_response("이해하지 못했습니다. 식사 입력이나 식단 추천을 요청해주세요.")
            
        except Exception as e:
            print(f"입력 처리 중 오류 발생: {e}")
            return self._create_error_response("처리 중 오류가 발생했습니다.")
            
    async def _analyze_intent_with_llm(self, user_input: str) -> Dict[str, Any]:
        """LLM을 사용하여 사용자 입력의 의도를 분석"""
        try:
            prompt = get_analyze_input_prompt(user_input)
            # print(f"의도 분석 프롬프트: {prompt}")  # 디버깅용 로그 추가
            
            response = await self.llm.ainvoke(prompt)
            # print(f"LLM 응답: {response.content}")  # 디버깅용 로그 추가
            
            # JSON 부분만 추출
            start_idx = response.content.find('{')
            end_idx = response.content.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON 형식이 올바르지 않습니다.")
            
            json_str = response.content[start_idx:end_idx]
            result = json.loads(json_str)
            # print(f"파싱된 JSON: {result}")  # 디버깅용 로그 추가
            
            # 기본값 설정
            default_values = {
                "intent": "식사 기록",
                "meal_time": "간식",
                "food_name": "",
                "portion": "",
                "additional_info": {}
            }
            
            # 값이 없는 필드는 기본값으로 설정
            for key, default_value in default_values.items():
                if key not in result or result[key] is None:
                    result[key] = default_value
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return default_values
        except Exception as e:
            print(f"의도 분석 중 오류 발생: {e}")
            return default_values

class AgentState(BaseModel):
    """에이전트 상태"""
    user_id: str = Field(default="")
    meal_type: str = Field(default="")
    food_input: str = Field(default="")
    meal_items: List[Dict[str, Any]] = Field(default_factory=list)
    total_nutrition: Dict[str, float] = Field(default_factory=dict)
    nutrition_analysis: Dict[str, Any] = Field(default_factory=dict)
    food_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)

    class Config:
        validate_assignment = True
 