"""
일반 에이전트 노드 함수
일반적인 사용자 질문을 처리하는 LangGraph 노드 함수
"""

import logging
import time
from typing import Dict, Any, cast

from supervisor.agents.general_agent import GeneralAgent
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger(__name__)

def general_agent_node(state: GymGGunState, agent: GeneralAgent) -> GymGGunState:
    """
    일반 에이전트 노드 함수
    
    Args:
        state: 현재 파이프라인 상태
        agent: 일반 에이전트 인스턴스
    
    Returns:
        업데이트된 상태
    """
    logger.info(f"일반 에이전트 노드 실행 - 메시지: '{state.message}'")
    
    start_time = time.time()
    
    try:
        # 에이전트에 메시지 처리 요청
        result = agent.process(state.message, email=state.email)
        
        # 응답 추출
        if isinstance(result, dict) and "response" in result:
            response = result["response"]
        else:
            response = "질문에 대한 답변을 생성하는 중 오류가 발생했습니다."
            logger.error(f"일반 에이전트 응답 형식 오류: {result}")
        
        # 상태 업데이트
        state.response = response
        state.response_type = "general"
        state.end_time = time.time()
        
        # 메트릭 추가
        execution_time = time.time() - start_time
        state.metrics["general_agent_time"] = execution_time
        logger.info(f"일반 에이전트 처리 완료 - 실행 시간: {execution_time:.2f}초")
        
    except Exception as e:
        error_msg = f"일반 에이전트 처리 중 오류 발생: {str(e)}"
        logger.exception(error_msg)
        
        # 오류 상태 설정
        state.error = error_msg
        state.response = "질문을 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        state.end_time = time.time()
    
    return state 