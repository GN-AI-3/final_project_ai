"""
식단 관리 에이전트

이 모듈은 식단 관리 에이전트를 정의합니다.
"""
from typing import Dict, Any, List, Optional, Tuple, ClassVar
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain.schema import AIMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks.manager import CallbackManager
from langgraph.graph import Graph, StateGraph
import json
import os
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import logging
import traceback
import sys
from datetime import datetime
import uuid

from agents.food.tools.db_utils import get_user_info

# from .workflow import run_food_workflow, DietWorkflow
# # from .prompts.analyze_input_prompt import get_analyze_input_prompt
# # from .enums import IntentType, parse_intent_type

# # LangSmith 설정
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = "food-agent"

# # 로깅 설정
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# # 콘솔 핸들러 추가
# console_handler = logging.StreamHandler(sys.stdout)
# console_handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)

# # 파일 핸들러 추가
# file_handler = logging.FileHandler('food_agent.log')
# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)


# @dataclass
# class Intent:
#     """의도 정보"""
#     type: IntentType
#     meal_time: Optional[str] = None
#     food_name: Optional[str] = None
#     portion: Optional[float] = None
#     additional_info: Optional[Dict[str, Any]] = None

class FoodAgent(BaseModel):
    """음식 관련 에이전트"""
    
    DEFAULT_MODEL: ClassVar[str] = "gpt-4o-mini"
    model: ChatOpenAI = Field(default=None)
    
    def __init__(self, model: ChatOpenAI = None, **data):
        """음식 에이전트 초기화"""
        super().__init__(**data)
        if model is None:
            self.model = ChatOpenAI(
                model=self.DEFAULT_MODEL,
                temperature=0.7
            )
        else:
            self.model = model
            
    async def process(self, user_input: str) -> Dict[str, Any]:
            user_id=3;
            print(f"사용자 정보 조회 시작: {user_id}")
            user_info = await get_user_info(user_id)
            print(f"사용자 정보: {user_info}")
            prompt = ChatPromptTemplate.from_messages([
                ("system", """
                당신은 영양 전문가입니다. 아래의 사용자 정보를 분석하여 최적의 답변을 내주세요.
                
                사용자 정보:
                {user_info}
                
                주의사항:
                1. 식단 유형은 사용자의 목표에 맞게 선택합니다.
                2. 각 식사는 균형 잡힌 영양소 비율을 가져야 합니다.
                """),
                ("user", "{message}"),
            ])
            chain = prompt | self.model
            response = await chain.ainvoke({
                "user_info": str(user_info),  # user_info가 dict면 str로 변환 필요
                "message": user_input,
            })
            print(f"응답: {response.content}")
            return {"type": "food", "response": response.content}
    #     """
    #     사용자 입력을 처리하고 응답을 생성합니다.
        
    #     Args:
    #         user_input: 사용자 입력 텍스트
            
    #     Returns:
    #         Dict[str, Any]: 처리 결과
    #     """
    #     try:
    #         member_id = "3" 
    #         logger.info(f"FoodAgent.process 시작: user_input={user_input}, member_id={member_id}")
            
    #         # 의도 분석
    #         intent = await self._analyze_intent(user_input)
    #         logger.info(f"분석된 의도: {intent}")
            
    #         # 워크플로우 실행
    #         result = await run_food_workflow(
    #             input_text=user_input,
    #             member_id=str(member_id),
    #             meal_type=intent.meal_time if intent.meal_time else "",
    #             model=self.llm
    #         )
            
    #         logger.info(f"워크플로우 실행 결과: {result}")
    #         return result
            
        # except Exception as e:
        #     logger.error(f"FoodAgent.process 실행 중 오류 발생: {str(e)}")
        #     logger.error(traceback.format_exc())
        #     return {
        #         "status": "error",
        #         "error": str(e)
        #     }
    
#     async def process_input(self, user_input: str, member_id: str) -> Dict[str, Any]:
#         """
#         사용자 입력을 처리합니다.
        
#         Args:
#             user_input: 사용자 입력
#             member_id: 사용자 ID
            
#         Returns:
#             처리 결과
#         """
#         try:
#             # 입력 검증
#             if not user_input or not member_id:
#                 return {"error": "입력이 유효하지 않습니다."}
                
#             # 워크플로우 실행
#             result = await run_food_workflow(
#                 input_text=user_input,
#                 member_id=member_id,
#                 model=self.llm  # 초기화된 LLM을 워크플로우에 전달
#             )
            
#             return result
            
#         except Exception as e:
#             return {"error": f"입력 처리 중 오류 발생: {str(e)}"}
            
#     def _create_error_response(self, message: str) -> Dict[str, Any]:
#         """에러 응답 생성"""
#         return {
#             "type": "food",
#             "response": f"죄송합니다. {message}"
#         }

# class AgentState(BaseModel):
#     """에이전트 상태"""
#     member_id: str = Field(default="")
#     meal_type: str = Field(default="")
#     food_input: str = Field(default="")
#     meal_items: List[Dict[str, Any]] = Field(default_factory=list)
#     total_nutrition: Dict[str, float] = Field(default_factory=dict)
#     nutrition_analysis: Dict[str, Any] = Field(default_factory=dict)
#     food_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
#     error: Optional[str] = Field(default=None)

#     class Config:
#         validate_assignment = True
 