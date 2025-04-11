"""
결과 통합 노드
주 에이전트와 보조 에이전트 결과를 통합하는 노드 함수
"""

import logging
import traceback
import time
from supervisor.langgraph.state import GymGGunState

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.utils.result_combiner')

def result_combiner(state: GymGGunState) -> GymGGunState:
    """주 에이전트와 보조 에이전트 결과를 통합"""
    try:
        start_time = time.time()
        
        # 이미 agent_runner 노드에서 결과가 state에 저장되어 있으므로 
        # 여기서는 간단히 로그만 남기고 통과
        response = state.response
        response_type = state.response_type
        
        logger.debug(f"[RESULT_COMBINER] 입력 상태: type={response_type}, response={response[:50] if response else None}")
        logger.info(f"결과 통합 - 응답 타입: {response_type}, 응답 길이: {len(response) if response else 0}")
        
        # 메트릭에 실행 시간 기록
        execution_time = time.time() - start_time
        state.metrics["result_combiner_time"] = execution_time
        logger.debug(f"[RESULT_COMBINER] 결과 통합 완료: 실행 시간={execution_time:.2f}초")
        
        return state
        
    except Exception as e:
        error_msg = f"결과 통합 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        
        # 오류 정보 설정
        state.error = error_msg
        if not state.response:
            state.response = "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다."
            state.response_type = "error"
        
        return state 