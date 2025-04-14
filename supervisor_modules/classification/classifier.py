"""
분류 모듈
메시지 분류 기능을 제공합니다.
"""

import time
import json
import traceback
import os
import logging
from typing import Dict, Any, List, Optional
from contextlib import nullcontext

import openai
from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage
from langsmith.run_helpers import traceable

# 로그 설정
logging.basicConfig(level=logging.INFO)

from supervisor_modules.state.state_manager import SupervisorState
from supervisor_modules.utils.logger_setup import get_logger
from chat_history_manager import ChatHistoryManager
from common_prompts.prompts import CATEGORY_CONTEXT_PROMPT

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# 로거 설정
logger = get_logger(__name__)

# 채팅 내역 관리자 초기화
chat_history_manager = ChatHistoryManager()

@traceable(run_type="chain", name="메시지 분류")
async def classify_message(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 메시지를 분류하여 적절한 에이전트 카테고리를 할당합니다.
    이전 대화 내역을 고려하여 분류합니다.
    
    Args:
        state_dict: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    message = state.message
    email = state.email  # 사용자 이메일
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 메시지 분류 시작: '{message[:50]}...'")
        
        # 이전 대화 내역 가져오기
        chat_history = []
        formatted_history = ""
        
        if email:
            # 최근 대화 내역 가져오기 (최대 5개)
            chat_history = chat_history_manager.get_recent_messages(email, 5)
            
            # 대화 내역 포맷팅
            if chat_history:
                for entry in chat_history:
                    role = "사용자" if entry.get("role", "") == "user" else "AI"
                    content = entry.get("content", "")
                    formatted_history += f"{role}: {content}\n"
        
        # LangChain 모델 초기화
        chat_model = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.1
        )
        
        # 시스템 프롬프트 설정
        system_prompt = CATEGORY_CONTEXT_PROMPT
        
        # 모델 호출을 위한 메시지 설정
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message)
        ]
        
        # 모델 호출 (대화 내역 포함)
        response = chat_model.invoke(messages, {"message": message, "chat_history": formatted_history})
        
        # 결과 파싱
        response_text = response.content.strip()
        logger.info(f"LLM 분류 응답: {response_text}")
        
        try:
            # JSON 배열 파싱
            categories = json.loads(response_text)
            
            # 유효한 카테고리 목록
            valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
            
            # 유효한 카테고리만 필터링
            filtered_categories = [cat for cat in categories if cat in valid_categories]
            
            # 카테고리가 없으면 기본값 사용
            if not filtered_categories:
                filtered_categories = ["general"]
                logger.warning(f"[{request_id}] 유효한 카테고리가 없어 'general'로 기본 설정")
            
            # 상태 업데이트
            state.categories = filtered_categories
            state.selected_agents = filtered_categories  # 현재는 카테고리와 에이전트를 1:1로 매핑
            
            logger.info(f"[{request_id}] LLM 메시지 분류 완료: {filtered_categories}")
            
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본 카테고리로 "general" 사용
            logger.warning(f"[{request_id}] JSON 파싱 실패: {response_text}, 기본 카테고리 'general' 사용")
            state.categories = ["general"]
            state.selected_agents = ["general"]
            
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 분류 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 카테고리 사용
        state.categories = ["general"]
        state.selected_agents = ["general"]
        state.metrics["classification_error"] = str(e)
        state.metrics["classification_time"] = time.time() - start_time
    
    # 메트릭 기록
    state.metrics["classification_time"] = time.time() - start_time
    logger.info(f"[{request_id}] 메시지 분류 완료: {state.categories} (소요시간: {time.time() - start_time:.2f}초)")
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict() 