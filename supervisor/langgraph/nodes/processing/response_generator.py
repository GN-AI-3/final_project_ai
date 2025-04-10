"""
응답 생성 노드
최종 사용자 응답을 생성하는 노드 함수
"""

import logging
import traceback
import time
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.processing.response_generator')

def response_generator(state: GymGGunState) -> GymGGunState:
    """최종 응답 생성 및 응답 형식화"""
    try:
        start_time = time.time()
        
        # state에서 응답 데이터 가져오기
        response_message = state.response or "죄송합니다. 응답을 생성할 수 없습니다."
        response_type = state.response_type or "general"
        
        logger.debug(f"[RESPONSE_GENERATOR] 입력 상태: type={response_type}, response={response_message[:50]}...")
        logger.info(f"응답 생성 처리 중 - 타입: {response_type}")
        
        # 기본 응답 사전 정의
        default_responses = {
            "exercise": "운동 추천을 처리 중입니다. 잠시 후 다시 시도해주세요.",
            "food": "식단 정보를 처리 중입니다. 잠시 후 다시 시도해주세요.",
            "diet": "다이어트 정보를 처리 중입니다. 잠시 후 다시 시도해주세요.",
            "schedule": "일정 정보를 처리 중입니다. 잠시 후 다시 시도해주세요.",
            "motivation": "동기부여 메시지를 생성 중입니다. 잠시 후 다시 시도해주세요.",
            "general": "요청을 처리 중입니다. 잠시 후 다시 시도해주세요."
        }
        
        # 비동기 에이전트 응답 패턴 감지 및 기본 응답으로 대체
        if "비동기 에이전트 응답" in response_message or "동기 처리" in response_message:
            logger.debug(f"[RESPONSE_GENERATOR] 비동기 응답 패턴 감지: '{response_message[:50]}...'")
            if response_type in default_responses:
                original_response = response_message
                response_message = default_responses[response_type]
                logger.info(f"비동기 응답 감지: 타입 {response_type}에 대한 기본 응답으로 대체")
                logger.debug(f"[RESPONSE_GENERATOR] 응답 교체: '{original_response[:30]}...' -> '{response_message}'")
                # 상태 업데이트
                state.response = response_message
        
        # 실행 시간 메트릭 기록
        execution_time = time.time() - start_time
        state.metrics["response_generator_time"] = execution_time
        logger.info(f"응답 생성 완료 - 실행 시간: {execution_time:.2f}초")
        logger.debug(f"[RESPONSE_GENERATOR] 최종 응답: type={response_type}, response={response_message[:50]}...")
        
        return state
        
    except Exception as e:
        error_msg = f"응답 생성 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        
        # 오류 정보 설정
        state.error = error_msg
        state.response = "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다."
        state.response_type = "error"
        
        return state 