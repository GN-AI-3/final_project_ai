"""
Supervisor 모듈
에이전트 관리, 분류, 실행을 총괄하는 모듈입니다.
다중 에이전트 병렬 처리를 지원합니다.
"""

import logging
import traceback
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from langchain_core.language_models import BaseChatModel
from chat_history_manager import ChatHistoryManager

# LangGraph 파이프라인 임포트
from supervisor.langgraph_pipeline import LangGraphPipeline

logger = logging.getLogger(__name__)

# 카테고리 분류를 위한 시스템 프롬프트
CATEGORY_SYSTEM_PROMPT = """당신은 사용자의 메시지를 분석하고 적절한 카테고리로 분류하는 도우미입니다.
사용자의 메시지를 다음 카테고리 중 적합한 카테고리를 모두 찾아서 분류해야 합니다:

1. exercise: 운동, 피트니스, 트레이닝, 근육, 스트레칭, 체력, 운동 루틴, 운동 계획, 운동 방법, 요일별 운동 추천, 운동 일정 계획, 운동 프로그램 등에 관련된 질문
2. food: 음식, 식단, 영양, 요리, 식품, 건강식, 식이요법, 다이어트 식단, 영양소 등에 관련된 질문
3. diet: 체중 감량, 체중 조절, 칼로리 관리, 체지방 감소, 체형 관리 목표 등에 관련된 질문
4. schedule: PT 예약, 트레이닝 세션 일정, 코치 미팅 스케줄, 피트니스 클래스 등록, 헬스장 방문 일정 등 실제 일정 관리에 관련된 질문
5. motivation: 동기 부여, 의지 강화, 습관 형성, 마음가짐, 목표 설정 등에 관련된 질문
6. general: 위 카테고리에 명확하게 속하지 않지만 건강/피트니스와 관련된 일반 대화

분류 시 주의사항:
- 운동 루틴이나 운동 계획, 요일별 운동 추천, 주간 운동 계획 등은 모두 schedule이 아닌 exercise 카테고리로 분류하세요.
- 요일별 식단이나 식단 계획은 food 카테고리로 분류하세요.
- schedule 카테고리는 실제 PT 예약, 코치 미팅, 피트니스 클래스 참여와 같은 구체적인 일정 관리에만 사용하세요.
- diet 카테고리는 체중 감량이나 체형 관리 목표에 관한 내용으로 제한하세요.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천해줘"와 같은 질문은 exercise 카테고리입니다.
- "이번주 월,수,금에 운동할건데 식단 추천해줘"와 같은 질문은 food 카테고리입니다.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천이랑 식단 같이 짜줘"와 같은 질문은 exercise와 food 카테고리입니다.

제공된 사용자 메시지를 분석하고 관련된 모든 카테고리를 JSON 배열 형식으로 반환하세요.
예: ["exercise", "diet"], ["food"], ["motivation"]

사용자 메시지가 여러 카테고리에 해당할 수 있으며, 최대 3개까지의 관련 카테고리를 반환하세요.
동시에 여러 주제를 언급한 경우, 관련된 모든 카테고리를 포함해야 합니다.
예를 들어, "운동과 식단 계획을 알려줘"는 ["exercise", "food"]과 같이 분류될 수 있습니다."""

# 에이전트 프롬프트 템플릿 (대화 맥락 포함)
AGENT_CONTEXT_PROMPT = """당신은 전문 AI 피트니스 코치입니다. 이전 대화 내용을 고려하여 사용자의 질문에 답변해 주세요.

이전 대화 내역:
{chat_history}

사용자의 새 질문: {message}

답변 시 이전 대화의 맥락을 고려하여 일관되고 개인화된 답변을 제공하세요."""

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
        # 대화 내역 관리자 초기화
        self.chat_history_manager = ChatHistoryManager()
        # LangGraph 파이프라인 초기화
        self.pipeline = LangGraphPipeline(agents=self.agents, llm=self.model)
        logger.info("Supervisor 초기화 완료")
    
    def register_agent(self, category: str, agent: Any) -> None:
        """
        에이전트를 특정 카테고리에 등록합니다.
        
        Args:
            category: 에이전트가 처리할 메시지 카테고리
            agent: 등록할 에이전트 객체
        """
        self.agents[category] = agent
        # LangGraph 파이프라인에도 등록
        self.pipeline.register_agent(category, agent)
        logger.info(f"카테고리 '{category}'에 에이전트 등록 완료")
    
    async def process(self, message: str, email: str = None, **kwargs) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 적절한 에이전트(들)로 라우팅합니다.
        
        Args:
            message: 처리할 사용자 메시지
            email: 사용자 이메일 (선택사항)
            
        Returns:
            Dict[str, Any]: 처리 결과
        """
        start_time = time.time()
        
        try:
            logger.info(f"메시지 처리 시작: {message[:50]}...")
            
            # 대화 내역 가져오기
            chat_history = None
            if email:
                try:
                    chat_history = await self.chat_history_manager.get_chat_history(email)
                    logger.info(f"대화 내역 로드 완료 - 이메일: {email}, 항목 수: {len(chat_history) if chat_history else 0}")
                except Exception as e:
                    logger.error(f"대화 내역 로드 오류: {str(e)}")
                    # 오류가 발생해도 계속 진행
            
            # LangGraph 파이프라인을 통한 메시지 처리
            result = await self.pipeline.process(message, email=email, chat_history=chat_history)
            
            # 대화 내역 저장 (성공적인 경우에만)
            if email and result.get("response"):
                try:
                    await self.chat_history_manager.add_chat_entry(
                        email=email,
                        user_message=message,
                        ai_response=result["response"]
                    )
                    logger.info(f"대화 내역 업데이트 완료 - 이메일: {email}")
                except Exception as e:
                    logger.error(f"대화 내역 저장 오류: {str(e)}")
            
            # 처리 시간 추가
            execution_time = time.time() - start_time
            result["execution_time"] = execution_time
            
            logger.info(f"메시지 처리 완료 - 실행 시간: {execution_time:.2f}초")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"메시지 처리 중 오류: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            return {
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다.",
                "type": "error",
                "error": str(e),
                "execution_time": execution_time
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 정보를 반환합니다."""
        return self.pipeline.get_metrics() 