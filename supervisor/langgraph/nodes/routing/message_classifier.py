"""
메시지 분류기 노드
사용자 메시지를 분석하여 적절한 카테고리로 분류하는 노드 함수
"""

import logging
import traceback
import time
from supervisor.langgraph.state import GymGGunState
from supervisor.llm import LLM

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.routing.message_classifier')

def message_classifier(state: GymGGunState, llm: LLM) -> GymGGunState:
    """사용자 메시지를 분석하여 카테고리 분류"""
    try:
        start_time = time.time()
        message = state.message
        
        logger.debug(f"[MESSAGE_CLASSIFIER] 입력 상태: message={message[:30]}...")
        logger.info(f"메시지 분류 시작 - 메시지: {message[:30]}...")
        
        # LLM을 사용하여 메시지 유형 분류
        # 현재는 간단한 키워드 기반 분류기로 대체
        keywords = {
            "exercise": ["운동", "웨이트", "근육", "스트레칭", "헬스", "체력", "유산소", "근력"],
            "food": ["식단", "음식", "식사", "영양", "단백질", "영양소", "먹다", "먹을", "섭취"],
            "diet": ["다이어트", "식이요법", "체중", "감량", "칼로리", "체지방", "체중 감량", "식이 조절"],
            "schedule": ["일정", "스케줄", "계획", "루틴", "시간표", "프로그램", "순서", "시간 관리"],
            "motivation": ["동기", "의욕", "노력", "성취", "목표", "꾸준히", "습관", "결심"]
        }
        
        # 간단한 의도 분류
        message_type = "general"
        for cat, words in keywords.items():
            for word in words:
                if word in message:
                    message_type = cat
                    break
            if message_type != "general":
                break
                
        # 결과 기록
        logger.info(f"메시지 분류 결과: {message_type}")
        logger.debug(f"[MESSAGE_CLASSIFIER] 분류 결과: message_type={message_type}")
        
        # 실행 시간 기록
        execution_time = time.time() - start_time
        logger.info(f"메시지 분류 완료 - 실행 시간: {execution_time:.2f}초")
        
        # 상태 업데이트
        state.classified_type = message_type
        state.metrics["message_classifier_time"] = execution_time
        logger.debug(f"[MESSAGE_CLASSIFIER] 출력 상태: classified_type={state.classified_type}")
        
        return state
    except Exception as e:
        error_msg = f"메시지 분류 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        # 오류 발생 시 기본값 반환
        state.classified_type = "general"
        state.error = f"메시지 분류 오류: {str(e)}"
        return state 