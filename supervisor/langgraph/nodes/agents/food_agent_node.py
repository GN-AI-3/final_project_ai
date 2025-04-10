"""
음식 에이전트 노드 함수
음식과 관련된 사용자 질문을 처리하는 LangGraph 노드 함수
"""

import logging
import time
from typing import Dict, Any, cast

from supervisor.agents.food_agent import FoodAgent
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.food_agent')

def food_agent_node(state: GymGGunState, agent: FoodAgent) -> GymGGunState:
    """
    음식 에이전트 노드 함수
    
    Args:
        state: 현재 파이프라인 상태
        agent: 음식 에이전트 인스턴스
    
    Returns:
        업데이트된 상태
    """
    logger.debug(f"[FOOD_AGENT] 입력 상태: email={state.email}, message={state.message[:30]}...")
    logger.info(f"음식 에이전트 노드 실행 - 메시지: '{state.message}'")
    
    start_time = time.time()
    
    try:
        # 에이전트에 메시지 처리 요청
        logger.debug(f"[FOOD_AGENT] 에이전트에 메시지 전달: {state.message[:50]}...")
        result = agent.process(state.message, email=state.email)
        logger.debug(f"[FOOD_AGENT] 에이전트 응답 결과: {str(result)[:200]}...")
        
        # 응답 추출
        if isinstance(result, dict) and "response" in result:
            response = result["response"]
            logger.debug(f"[FOOD_AGENT] 응답 추출 성공: {response[:50]}...")
        else:
            response = "음식 관련 질문에 대한 답변을 생성하는 중 오류가 발생했습니다."
            logger.error(f"음식 에이전트 응답 형식 오류: {result}")
        
        # 상태 업데이트
        state.response = response
        state.response_type = "food"
        state.end_time = time.time()
        
        # 메트릭 추가
        execution_time = time.time() - start_time
        state.metrics["food_agent_time"] = execution_time
        logger.info(f"음식 에이전트 처리 완료 - 실행 시간: {execution_time:.2f}초")
        logger.debug(f"[FOOD_AGENT] 출력 상태: response_type={state.response_type}, response={state.response[:50]}...")
        
    except Exception as e:
        error_msg = f"음식 에이전트 처리 중 오류 발생: {str(e)}"
        logger.exception(error_msg)
        
        # 오류 상태 설정
        state.error = error_msg
        state.response = "음식 관련 질문을 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        state.end_time = time.time()
    
    return state 