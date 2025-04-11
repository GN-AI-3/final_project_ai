"""
LangGraph 기반 파이프라인 모듈
여러 에이전트를 효율적으로 연결하고 메시지와 컨텍스트를 처리하는 그래프 구조
"""

import logging
import traceback
import json
from typing import Dict, List, Any, Optional, Annotated, Sequence, TypedDict
import os
from datetime import datetime
import time
import asyncio

# LangGraph 관련 임포트
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, chain
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# 노드 임포트
from supervisor.langgraph.nodes.routing.message_classifier import message_classifier
from supervisor.langgraph.nodes.routing.message_router import message_router
from supervisor.langgraph.nodes.processing.agent_runner import agent_runner
from supervisor.langgraph.nodes.processing.response_generator import response_generator
from supervisor.langgraph.nodes.utils.context_loader import context_loader
from supervisor.langgraph.nodes.utils.result_combiner import result_combiner

# 상태 클래스 임포트
from supervisor.langgraph.state import GymGGunState

# 로거 설정
logger = logging.getLogger(__name__)

# -----------------------------
# 워크플로우 생성 함수
# -----------------------------
def create_workflow(agents=None, llm=None):
    """전체 파이프라인 워크플로우 그래프 생성"""
    # 기본 상태 그래프 생성
    workflow = StateGraph(GymGGunState)
    
    # 노드 추가
    workflow.add_node("message_classifier", lambda state: message_classifier(state, llm))
    workflow.add_node("context_loader", context_loader)
    workflow.add_node("agent_runner", lambda state: agent_runner(state, agents))
    workflow.add_node("result_combiner", result_combiner)
    workflow.add_node("response_generator", response_generator)
    
    # 엣지 연결 (워크플로우 정의)
    workflow.add_edge("message_classifier", "context_loader")
    workflow.add_edge("context_loader", "agent_runner")
    workflow.add_edge("agent_runner", "result_combiner")
    workflow.add_edge("result_combiner", "response_generator")
    workflow.add_edge("response_generator", END)
    
    # 시작 노드 설정
    workflow.set_entry_point("message_classifier")
    
    # 컴파일된 그래프 반환
    return workflow.compile()

# -----------------------------
# 파이프라인 클래스
# -----------------------------
class LangGraphPipeline:
    """LangGraph 기반 파이프라인"""
    
    def __init__(self, agents=None, llm=None):
        """LangGraphPipeline 초기화"""
        self.agents = agents or {}
        self.llm = llm
        self.graph = create_workflow(agents=self.agents, llm=self.llm)
        self.metrics = {
            "requests_processed": 0,
            "successful_responses": 0,
            "failed_responses": 0,
            "avg_processing_time": 0
        }
        logger.info("LangGraphPipeline 초기화 완료")
    
    def register_agent(self, category: str, agent: Any) -> None:
        """에이전트를 파이프라인에 등록합니다."""
        self.agents[category] = agent
        # 그래프 재생성
        self.graph = create_workflow(agents=self.agents, llm=self.llm)
        logger.info(f"에이전트 등록 완료: {category}")
    
    async def process(self, message: str, email: str = None, chat_history: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        메시지 처리 파이프라인을 실행합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항)
            chat_history: 대화 내역 (선택사항)
            
        Returns:
            Dict[str, Any]: 처리 결과
        """
        start_time = time.time()
        logger.info(f"메시지 처리 파이프라인 시작 - 이메일: {email or '익명'}")
        
        try:
            # 메시지 인코딩 문제 방지를 위한 처리
            try:
                message = message.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"메시지 인코딩 처리 중 오류: {str(e)}")
            
            # 초기 상태 객체 생성
            state = GymGGunState(
                message=message,
                email=email or "anonymous@example.com",
                start_time=start_time
            )
            
            # 대화 내역 설정 (있는 경우)
            if chat_history:
                # 파이썬 객체에 직접 할당은 불가능하므로 상태의 set 메소드 사용
                state.set("chat_history", chat_history)
                logger.info(f"대화 내역 설정 완료 - 항목 수: {len(chat_history)}")
            
            # 그래프 실행 (동기적으로)
            result_state = self.graph.invoke(state)
            
            # 실행 시간 계산
            execution_time = time.time() - start_time
            
            # 상태에서 응답 정보 추출
            response = result_state.response or "처리 중 오류가 발생했습니다."
            response_type = result_state.response_type or "general"
            
            # 성공 여부 확인
            is_success = result_state.response is not None and not result_state.error
            
            # 메트릭 업데이트
            self.metrics["requests_processed"] += 1
            if is_success:
                self.metrics["successful_responses"] += 1
            else:
                self.metrics["failed_responses"] += 1
            
            # 평균 처리 시간 업데이트
            count = self.metrics["successful_responses"] + self.metrics["failed_responses"]
            self.metrics["avg_processing_time"] = (
                (self.metrics["avg_processing_time"] * (count - 1) + execution_time) / count
            )
            
            # 최종 결과 객체 구성
            result = {
                "response": response,
                "type": response_type,
                "execution_time": execution_time,
                "metrics": result_state.metrics,
                "error": result_state.error
            }
            
            logger.info(f"파이프라인 처리 완료 - 실행 시간: {execution_time:.2f}초")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"파이프라인 처리 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 메트릭 업데이트
            self.metrics["requests_processed"] += 1
            self.metrics["failed_responses"] += 1
            
            # 오류 응답 반환
            return {
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다.",
                "type": "error",
                "error": str(e),
                "execution_time": execution_time
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """파이프라인 메트릭을 반환합니다."""
        return self.metrics 