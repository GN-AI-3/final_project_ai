"""
메시지 라우터 노드
메시지 타입을 기반으로 적절한 에이전트로 라우팅하는 노드 함수
"""

import logging
import traceback
import time
from typing import Literal
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.routing.message_router')

def message_router(state: GymGGunState) -> Literal["exercise", "food", "diet", "schedule", "motivation", "general"]:
    """메시지 타입에 따라 라우팅 결정"""
    try:
        start_time = time.time()
        message = state.message
        message_type = state.classified_type
        
        logger.debug(f"[MESSAGE_ROUTER] 입력 상태: message_type={message_type}, message={message[:30]}...")
        logger.info(f"메시지 라우팅 - 타입: {message_type}, 메시지: {message[:30]}...")
        
        # 실행 시간 기록
        execution_time = time.time() - start_time
        state.metrics["message_router_time"] = execution_time
        logger.info(f"메시지 라우팅 완료: {message_type} - 실행 시간: {execution_time:.2f}초")
        logger.debug(f"[MESSAGE_ROUTER] 라우팅 결정: {message_type}")
        
        return message_type
    except Exception as e:
        error_msg = f"메시지 라우팅 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        # 오류 발생 시 기본값 반환
        return "general" 