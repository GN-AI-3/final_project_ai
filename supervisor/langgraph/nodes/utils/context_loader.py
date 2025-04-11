"""
컨텍스트 로더 노드
사용자 컨텍스트 정보 및 채팅 기록을 로드하는 노드 함수
"""

import logging
import traceback
import time
import asyncio
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
        
        # state에 이미 chat_history가 있는지 확인
        chat_history = state.get("chat_history")
        
        # chat_history가 없는 경우에만 로드 시도
        if not chat_history:
            try:
                chat_history_manager = ChatHistoryManager()
                
                # 비동기 함수 호출을 위한 이벤트 루프 확인 및 실행
                try:
                    # 이벤트 루프가 이미 실행 중인지 확인
                    loop = asyncio.get_running_loop()
                    logger.info("이벤트 루프가 이미 실행 중입니다. 동기적으로 처리합니다.")
                    # 동기적으로 처리
                    messages = chat_history_manager.get_recent_messages(email, limit=10)
                except RuntimeError:
                    # 이벤트 루프가 없으면 새로 만들어서 실행
                    logger.info("새 이벤트 루프를 생성하여 비동기 처리합니다.")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    messages = loop.run_until_complete(
                        chat_history_manager.get_chat_history(email)
                    )
                    
                chat_history = messages
                # 대화 내역을 상태에 저장
                state.set("chat_history", chat_history)
                logger.info(f"채팅 기록 로드 완료 - {len(messages)}개 메시지")
                logger.debug(f"[CONTEXT_LOADER] 채팅 기록: {len(messages)}개 메시지 로드됨")
                
                # 메트릭에 채팅 기록 정보 추가
                state.metrics["chat_history_count"] = len(messages)
            except Exception as e:
                logger.error(f"채팅 기록 로드 오류: {str(e)}")
                # 오류 발생해도 계속 진행
                state.metrics["chat_history_error"] = str(e)
                logger.debug(f"[CONTEXT_LOADER] 채팅 기록 로드 실패: {str(e)}")
        else:
            # 이미 chat_history가 있는 경우 로깅
            logger.info(f"채팅 기록이 이미 로드되어 있습니다 - {len(chat_history)}개 메시지")
            state.metrics["chat_history_count"] = len(chat_history)
        
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