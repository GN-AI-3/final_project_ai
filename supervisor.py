"""
Supervisor 모듈
에이전트 관리, 분류, 실행을 총괄하는 모듈입니다.
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

# 카테고리 분류를 위한 시스템 프롬프트
CATEGORY_SYSTEM_PROMPT = """당신은 사용자의 메시지를 분석하고 적절한 카테고리로 분류하는 도우미입니다.
사용자의 메시지를 다음 카테고리 중 하나로 분류해야 합니다:

1. exercise: 운동, 피트니스, 트레이닝, 근육, 스트레칭, 체력 등에 관련된 질문
2. food: 음식, 식단, 영양, 요리, 식품, 건강식 등에 관련된 질문
3. diet: 체중 감량, 다이어트, 칼로리 관리, 체중 조절 등에 관련된 질문
4. schedule: 운동 루틴, 일정 관리, 스케줄링, 계획 등에 관련된 질문
5. motivation: 동기 부여, 의지 강화, 습관 형성, 마음가짐 등에 관련된 질문
6. general: 위 카테고리에 명확하게 속하지 않지만 건강/피트니스와 관련된 일반 대화

제공된 사용자 메시지를 분석하고 가장 적절한 카테고리만 선택하여 해당 카테고리 키워드만 응답하세요.
예: "exercise", "food", "diet", "schedule", "motivation", "general"

사용자 메시지가 여러 카테고리에 해당할 수 있으나, 가장 주된 의도와 연관된 하나의 카테고리만 선택하세요."""

# 에이전트 매니저 클래스
class Supervisor:
    """에이전트 관리 및 메시지 라우팅을 위한 Supervisor 클래스"""
    
    def __init__(self, model: Optional[BaseChatModel] = None):
        """
        Supervisor 초기화
        
        Args:
            model: 카테고리 분류 및 응답 생성에 사용할 LLM
        """
        self.agents = {}
        self.model = model
        self.category_prompt = PromptTemplate(
            input_variables=["message"],
            template="{message}"
        )
        self.category_chain = LLMChain(
            llm=self.model,
            prompt=self.category_prompt
        )
        logger.info("Supervisor 초기화 완료")
    
    def register_agent(self, category: str, agent: Any) -> None:
        """
        에이전트를 특정 카테고리에 등록합니다.
        
        Args:
            category: 에이전트가 처리할 메시지 카테고리
            agent: 등록할 에이전트 객체
        """
        self.agents[category] = agent
        logger.info(f"카테고리 '{category}'에 에이전트 등록 완료")
    
    async def classify_message(self, message: str) -> str:
        """
        사용자 메시지를 분석하여 적절한 카테고리로 분류합니다.
        
        Args:
            message: 분류할 사용자 메시지
            
        Returns:
            str: 분류된 카테고리
        """
        try:
            logger.info(f"메시지 분류 시작: {message[:50]}...")
            
            # 간단한 키워드 기반 분류기
            keywords = {
                "exercise": ["운동", "웨이트", "근육", "스트레칭", "헬스", "체력", "유산소", "근력", "다이어트"],
                "food": ["식단", "음식", "식사", "영양", "단백질", "영양소", "먹다", "먹을", "섭취"],
                "diet": ["다이어트", "식이요법", "체중", "감량", "칼로리", "체지방", "체중 감량", "식이 조절"],
                "schedule": ["일정", "스케줄", "계획", "루틴", "시간표", "프로그램", "순서", "시간 관리"],
                "motivation": ["동기", "의욕", "노력", "성취", "목표", "꾸준히", "습관", "결심"]
            }
            
            # 간단한 의도 분류
            for category, words in keywords.items():
                for word in words:
                    if word in message:
                        logger.info(f"메시지 분류 결과 (키워드 기반): {category}")
                        return category
            
            # 키워드 분석으로 분류되지 않는 경우 LLM 사용
            if self.model:
                # 시스템 메시지와 사용자 메시지 준비
                messages = [
                    SystemMessage(content=CATEGORY_SYSTEM_PROMPT),
                    HumanMessage(content=message)
                ]
                
                # LLM을 통한 카테고리 분류
                response = await self.model.ainvoke(messages)
                category = response.content.strip().lower()
                
                # 유효한 카테고리인지 확인
                valid_categories = ["exercise", "food", "diet", "schedule", "motivation", "general"]
                if category not in valid_categories:
                    category = "general"  # 유효하지 않은 응답이면 general로 기본 설정
                
                logger.info(f"메시지 분류 결과 (LLM 기반): {category}")
                return category
            
            # LLM 없이 키워드로도 분류되지 않으면 general 반환
            logger.info("메시지 분류 결과: general (기본값)")
            return "general"
            
        except Exception as e:
            logger.error(f"메시지 분류 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return "general"  # 오류 발생 시 기본값으로 general 반환
    
    async def process(self, message: str, email: str = None, **kwargs) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 적절한 에이전트로 라우팅합니다.
        
        Args:
            message: 처리할 사용자 메시지
            email: 사용자 이메일 (선택사항)
            
        Returns:
            Dict[str, Any]: 처리 결과
        """
        start_time = time.time()
        try:
            logger.info(f"메시지 처리 시작 - 이메일: {email or '익명'}")
            
            # 1. 메시지 분류
            category = await self.classify_message(message)
            logger.info(f"메시지 분류 결과: {category}")
            
            # 2. 적절한 에이전트 선택
            if category in self.agents:
                agent = self.agents[category]
                logger.info(f"선택된 에이전트: {category}")
                
                # 3. 에이전트에 메시지 전달 - 매개변수 최소화
                try:
                    # 에이전트가 email을 지원하는지 시도해보고 안되면 email 없이 호출
                    if email is not None:
                        result = await agent.process(message, email=email)
                    else:
                        result = await agent.process(message)
                except TypeError as e:
                    # email 매개변수를 지원하지 않는 경우
                    logger.warning(f"{category} 에이전트 호출 중 TypeError: {str(e)}")
                    logger.info(f"{category} 에이전트는 email 매개변수를 지원하지 않습니다. 기본 호출 사용")
                    result = await agent.process(message)
                
                # 4. 결과 형식화 및 반환
                if isinstance(result, dict):
                    if "type" not in result:
                        result["type"] = category
                    if "execution_time" not in result:
                        result["execution_time"] = time.time() - start_time
                    logger.info(f"에이전트 처리 결과: 타입={result.get('type')}, 시간={result.get('execution_time'):.2f}초")
                    return result
                else:
                    # 문자열이나 다른 형식으로 반환된 경우, 딕셔너리로 변환
                    response = {
                        "response": str(result),
                        "type": category,
                        "execution_time": time.time() - start_time
                    }
                    logger.info(f"에이전트 처리 결과(문자열): 타입={category}, 시간={response['execution_time']:.2f}초")
                    return response
            else:
                # 등록된 에이전트가 없는 경우 일반 응답
                logger.warning(f"카테고리 '{category}'에 대한 등록된 에이전트 없음, 일반 응답 사용")
                return {
                    "response": "죄송합니다. 현재 이 질문에 답변할 수 있는 에이전트가 없습니다.",
                    "type": "general",
                    "execution_time": time.time() - start_time
                }
                
        except Exception as e:
            logger.error(f"메시지 처리 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 에러 발생 시에도 유효한 응답 반환
            return {
                "response": "죄송합니다. 메시지 처리 중 오류가 발생했습니다.",
                "type": "error",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Supervisor와 에이전트들의 성능 메트릭을 수집하여 반환합니다.
        
        Returns:
            Dict[str, Any]: 수집된 메트릭
        """
        metrics = {
            "agent_count": len(self.agents),
            "registered_categories": list(self.agents.keys())
        }
        
        # 각 에이전트별 메트릭 수집 (지원하는 경우)
        agent_metrics = {}
        for category, agent in self.agents.items():
            if hasattr(agent, "get_metrics") and callable(agent.get_metrics):
                try:
                    agent_metrics[category] = agent.get_metrics()
                except Exception as e:
                    logger.error(f"{category} 에이전트 메트릭 수집 중 오류: {str(e)}")
                    agent_metrics[category] = {"error": str(e)}
            else:
                agent_metrics[category] = {"metrics_supported": False}
        
        metrics["agent_metrics"] = agent_metrics
        return metrics 