"""
Supervisor 모듈 - 호환성 위한 래퍼 모듈
기존 코드와의 호환성을 위해 모듈화된 코드를 임포트하여 제공합니다.
"""

import logging
import os
import json
import asyncio
import uuid
import traceback
from typing import Dict, Any, List, Optional, Callable, Coroutine, Tuple
from datetime import datetime

# 환경변수 설정
MAX_RESPONSE_LENGTH = 8000
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

try:
    import openai
    from langchain_openai import ChatOpenAI
except ImportError:
    logging.warning("OpenAI 관련 라이브러리를 찾을 수 없습니다.")

# 모듈화된 코드 임포트
from supervisor_modules.state.state_manager import SupervisorState
from supervisor_modules.classification.classifier import classify_message
from supervisor_modules.agents_manager.agents_executor import (
    execute_agents, route_message, process_message, register_agent
)
from supervisor_modules.response.response_generator import generate_response
from common_prompts.prompts import AGENT_CONTEXT_PROMPT

# 로거 설정
def setup_logger():
    """LangGraph 모듈에 대한 로깅을 설정합니다."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 핸들러가 이미 설정되어 있는지 확인
    if logger.hasHandlers():
        return logger
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 설정
    try:
        log_file = "supervisor.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s (%(filename)s:%(lineno)d)',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"로그 파일 설정 중 오류 발생: {str(e)}")
    
    return logger

# 로그 초기화
logger = setup_logger()

# 클래스 대신 글로벌 변수 및 함수 사용
model = None
agents = {}

def set_model(llm_model):
    """
    전역 모델 설정
    """
    global model
    model = llm_model

# 기존 API 호환성 유지를 위한 함수
async def handle_message(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    기존 handle_message 함수 구현 - state_dict를 받아 처리
    """
    # 상태에서 메시지와 이메일 정보 추출
    state = SupervisorState.from_dict(state_dict)
    message = state.message
    email = state.email
    chat_history = state.chat_history
    
    # route_message 호출
    result = await process_message(message, email, chat_history)
    
    # state_dict에 결과 업데이트
    state_dict["response"] = result["response"]
    state_dict["categories"] = result["categories"]
    state_dict["selected_agents"] = result["selected_agents"]
    state_dict["metrics"] = result["metrics"]
    
    return state_dict

# API 서버에서 사용하는 인터페이스 함수
async def process_user_message(
    request_id: str, 
    message: str, 
    email: str = None, 
    chat_history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하는 API 인터페이스 함수
    
    Args:
        request_id: 요청 식별자
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        chat_history: 대화 기록 (선택 사항)
        
    Returns:
        처리 결과를 포함하는 딕셔너리
    """
    try:
        # route_message 함수 호출하여 처리
        result = await route_message(
            message=message,
            email=email,
            chat_history=chat_history
        )
        
        # 결과 반환
        return {
            "request_id": request_id,
            "response": result.get("response", ""),
            "categories": result.get("categories", []),
            "metrics": result.get("metrics", {})
        }
    except Exception as e:
        logger.error(f"Error in process_user_message: {str(e)}", exc_info=True)
        return {
            "request_id": request_id,
            "response": "죄송합니다, 메시지 처리 중 오류가 발생했습니다.",
            "categories": ["error"],
            "metrics": {"error": str(e)}
        }

# 이전 코드와의 호환성을 위한 Supervisor 클래스
class Supervisor:
    """
    에이전트 관리 및 메시지 처리를 담당하는 수퍼바이저 클래스
    호환성을 위해 유지되는 래퍼 클래스입니다.
    """
    def __init__(self, model: ChatOpenAI):
        """모델과 에이전트 초기화"""
        global agents
        # 모델 설정
        set_model(model)
        
        # 모델 안정성을 위해 직접 API 키 설정
        # SecretStr 타입이면 문자열로 변환
        if hasattr(model, 'openai_api_key'):
            api_key = model.openai_api_key
            # SecretStr 객체인 경우 문자열로 변환
            if hasattr(api_key, 'get_secret_value'):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key
    
    def register_agent(self, agent_type: str, agent_instance: Any) -> None:
        """
        에이전트를 시스템에 등록
        
        Args:
            agent_type: 에이전트 유형 (예: "exercise", "food" 등)
            agent_instance: 에이전트 인스턴스
        """
        register_agent(agent_type, agent_instance)
    
    async def process(self, message: str, email: str = None, chat_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하여 적절한 에이전트로 라우팅하고 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택 사항)
            chat_history: 채팅 기록 (선택 사항)
        
        Returns:
            Dict: 응답 및 메타데이터가 포함된 딕셔너리
        """
        result = await process_message(message, email, chat_history)
        return result 