"""
컨텍스트 로더 노드
사용자 컨텍스트 정보 및 채팅 기록을 로드하는 노드 함수
"""

import logging
import traceback
import time
from datetime import datetime
from supervisor.langgraph.state import GymGGunState
from chat_history_manager import ChatHistoryManager

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.utils.context_loader')

def context_loader(state: GymGGunState) -> GymGGunState:
    """사용자 컨텍스트 정보 및 채팅 기록 로드"""
    try:
        start_time = time.time()
        email = state.email
        classified_type = state.classified_type
        
        logger.debug(f"[CONTEXT_LOADER] 입력 상태: email={email}, classified_type={classified_type}")
        logger.info(f"컨텍스트 로더 시작 - 이메일: {email}, 카테고리: {classified_type}")
        
        # 메트릭에 컨텍스트 로드 시작 시간 설정
        state.metrics["context_load_start_time"] = start_time
        
        # 채팅 기록 로드
        chat_history = []
        try:
            chat_history_manager = ChatHistoryManager()
            messages = chat_history_manager.get_recent_messages(email, limit=10)
            chat_history = messages
            logger.info(f"채팅 기록 로드 완료 - {len(messages)}개 메시지")
            logger.debug(f"[CONTEXT_LOADER] 채팅 기록: {len(messages)}개 메시지 로드됨")
            
            # 메트릭에 채팅 기록 정보 추가
            state.metrics["chat_history_count"] = len(messages)
        except Exception as e:
            logger.error(f"채팅 기록 로드 오류: {str(e)}")
            # 오류 발생해도 계속 진행
            state.metrics["chat_history_error"] = str(e)
            logger.debug(f"[CONTEXT_LOADER] 채팅 기록 로드 실패: {str(e)}")
        
        # 메트릭에 채팅 기록 추가
        state.metrics["chat_history"] = chat_history
        
        # 사용자 컨텍스트 정보 메트릭에 추가
        user_context = {
            "email": email,
            "last_activity": datetime.now().isoformat()
        }
        state.metrics["user_context"] = user_context
        logger.debug(f"[CONTEXT_LOADER] 사용자 컨텍스트 추가: {user_context}")
        
        # 컨텍스트 로드 시간 기록
        execution_time = time.time() - start_time
        state.metrics["context_load_time"] = execution_time
        logger.debug(f"[CONTEXT_LOADER] 컨텍스트 로드 완료: 실행 시간={execution_time:.2f}초")
        
        return state
        
    except Exception as e:
        error_msg = f"컨텍스트 로드 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.exception(traceback.format_exc())
        
        # 오류 정보 설정
        state.error = error_msg
        
        return state 