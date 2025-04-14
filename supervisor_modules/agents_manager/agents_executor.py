"""
에이전트 실행 모듈
Supervisor에서 분류된 카테고리에 따라 적절한 에이전트를 호출하고 결과를 처리하는 기능을 제공합니다.
"""

import time
import traceback
import logging
import uuid
import asyncio
import os
from typing import Dict, Any, List
from contextlib import nullcontext

from langsmith.run_helpers import traceable

from supervisor_modules.state.state_manager import SupervisorState
from supervisor_modules.classification.classifier import classify_message

# 로거 설정
logger = logging.getLogger(__name__)

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# LangSmith 트레이서 초기화
try:
    tracer = traceable(project_name=os.getenv("LANGCHAIN_PROJECT"))
    logger.info(f"LangSmith 트레이서 초기화 성공 (프로젝트: {os.getenv('LANGCHAIN_PROJECT')})")
except Exception as e:
    logger.warning(f"LangSmith 트레이서 초기화 실패: {str(e)}")
    tracer = None

# 에이전트 프롬프트 템플릿 (대화 맥락 포함)
AGENT_CONTEXT_PROMPT = """당신은 전문 AI 피트니스 코치입니다. 이전 대화 내용을 고려하여 사용자의 질문에 답변해 주세요.

이전 대화 내역:
{chat_history}

사용자의 새 질문: {message}

답변 시 이전 대화의 맥락을 고려하여 일관되고 개인화된 답변을 제공하세요."""

# 전역 변수로 agents 선언
agents = {}

async def execute_agents(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    선택된 에이전트들 병렬 실행
    
    Args:
        state_dict: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    # 전역 변수 사용
    global agents
    
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    message = state.message
    chat_history = state.chat_history
    selected_agents = state.selected_agents
    
    start_time = time.time()
    agent_results = []
    
    try:
        logger.info(f"[{request_id}] 에이전트 병렬 실행 시작: {selected_agents}")
        
        # 선택된 에이전트가 없는 경우 기본 에이전트 사용
        if not selected_agents:
            selected_agents = ["general"]
            logger.warning(f"[{request_id}] 선택된 에이전트가 없어 기본 에이전트 사용")
        
        # 병렬 실행을 위한 태스크 목록 생성
        agent_tasks = []
        agent_names = []
        
        for agent_name in selected_agents:
            if agent_name not in agents:
                logger.warning(f"[{request_id}] 에이전트 '{agent_name}' 찾을 수 없음")
                continue
                
            agent = agents[agent_name]
            logger.info(f"[{request_id}] 에이전트 '{agent_name}' 태스크 생성")
            
            # 에이전트 실행 태스크 생성
            task = run_agent(request_id, agent_name, agent, message, chat_history)
            agent_tasks.append(task)
            agent_names.append(agent_name)
        
        if not agent_tasks:
            raise ValueError("실행할 수 있는 에이전트가 없습니다.")
        
        # 병렬 실행
        logger.info(f"[{request_id}] {len(agent_tasks)}개 에이전트 병렬 실행 중")
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)
        
        # 결과 처리
        for i, result in enumerate(results):
            agent_name = agent_names[i]
            
            if isinstance(result, Exception):
                # 예외 처리
                logger.error(f"[{request_id}] 에이전트 '{agent_name}' 실행 중 예외 발생: {str(result)}")
                agent_results.append({
                    "agent": agent_name,
                    "error": str(result),
                    "execution_time": 0
                })
            else:
                # 정상 결과 처리
                agent_results.append({
                    "agent": agent_name,
                    "result": result["result"],
                    "execution_time": result["execution_time"]
                })
                logger.info(f"[{request_id}] 에이전트 '{agent_name}' 실행 완료 (소요시간: {result['execution_time']:.2f}초)")
        
        # 상태 업데이트
        state.agent_results = agent_results
        state.metrics["agents_execution_time"] = time.time() - start_time
        logger.info(f"[{request_id}] 모든 에이전트 병렬 실행 완료 (총 소요시간: {time.time() - start_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"[{request_id}] 에이전트 병렬 실행 과정에서 심각한 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 심각한 오류 발생 시 상태 업데이트
        state.error = f"에이전트 실행 오류: {str(e)}"
        state.metrics["agents_execution_error"] = str(e)
        state.metrics["agents_execution_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict()

async def run_agent(request_id: str, agent_name: str, agent: Any, message: str, chat_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    단일 에이전트 실행을 위한 헬퍼 함수
    
    Args:
        request_id: 요청 식별자
        agent_name: 에이전트 이름
        agent: 에이전트 인스턴스
        message: 사용자 메시지
        chat_history: 대화 내역
        
    Returns:
        Dict[str, Any]: 에이전트 실행 결과
    """
    agent_start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 에이전트 '{agent_name}' 실행 중")
        
        # 에이전트 실행
        agent_result = await agent.process(
            message=message,
            chat_history=chat_history
        )
        
        execution_time = time.time() - agent_start_time
        
        return {
            "result": agent_result,
            "execution_time": execution_time
        }
        
    except Exception as e:
        logger.error(f"[{request_id}] 에이전트 '{agent_name}' 실행 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        raise e

async def route_message(
    message: str,
    email: str = None,
    chat_history: List[Dict[str, str]] = None,
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하여 적절한 에이전트로 라우팅하고 응답을 생성합니다.
    
    Args:
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        chat_history: 채팅 기록 (선택 사항)
        context: 추가 컨텍스트 정보 (선택 사항)
    
    Returns:
        Dict: 응답 및 메타데이터가 포함된 딕셔너리
    """
    global agents
    
    # 초기 상태 설정
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # 채팅 기록 초기화 (없는 경우)
    if chat_history is None:
        chat_history = []
    
    # 컨텍스트 초기화 (없는 경우)
    if context is None:
        context = {}
    
    # SupervisorState 초기화
    state = SupervisorState(
        request_id=request_id,
        message=message,
        email=email,
        chat_history=chat_history,
        context=context
    )
    
    logger.info(f"[{request_id}] 메시지 처리 시작: '{message[:50]}...' (길이: {len(message)})")
    
    try:
        # 메트릭 초기화
        metrics = {
            "start_time": start_time,
            "classification_time": 0,
            "agent_execution_time": 0,
            "response_generation_time": 0,
        }
        
        # 1. 메시지 분류 및 에이전트 선택
        state_dict = state.to_dict()
        state_dict = classify_message(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 2. 선택된 에이전트 실행
        state_dict = state.to_dict()
        state_dict = await execute_agents(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 3. 응답 생성
        from supervisor_modules.response.response_generator import generate_response
        state_dict = state.to_dict()
        state_dict = await generate_response(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 전체 실행 시간 계산
        total_time = time.time() - start_time
        state.metrics["total_execution_time"] = total_time
        
        logger.info(f"[{request_id}] 메시지 처리 완료 (소요시간: {total_time:.2f}초)")
        
        # 채팅 기록 저장 (필요한 경우)
        if email and isinstance(state.response, str):
            new_history_item = {
                "role": "user",
                "content": message
            }
            chat_history.append(new_history_item)
            
            new_history_item = {
                "role": "assistant",
                "content": state.response
            }
            chat_history.append(new_history_item)
        
        # 결과 반환
        return {
            "request_id": state.request_id,
            "response": state.response if isinstance(state.response, str) else "",
            "response_type": state.response_type if isinstance(state.response, str) else "text",
            "categories": state.categories if isinstance(state.categories, list) else [],
            "selected_agents": state.selected_agents if isinstance(state.selected_agents, list) else [],
            "metrics": state.metrics,
            "execution_time": total_time
        }
    
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 처리 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 응답 반환
        return {
            "request_id": request_id,
            "response": f"죄송합니다. 메시지를 처리하는 과정에서 오류가 발생했습니다: {str(e)}",
            "response_type": "error",
            "categories": [],
            "selected_agents": [],
            "metrics": {"error": str(e)},
            "execution_time": time.time() - start_time
        }

async def process_message(
    message: str,
    email: str = None,
    chat_history: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하여 적절한 에이전트로 라우팅하고 응답을 생성합니다.
    
    Args:
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        chat_history: 채팅 기록 (선택 사항)
    
    Returns:
        Dict: 응답 및 메타데이터가 포함된 딕셔너리
    """
    # route_message 함수를 호출하여 결과 반환
    return await route_message(message, email, chat_history)

def register_agent(agent_type: str, agent_instance: Any) -> None:
    """
    에이전트를 시스템에 등록
    
    Args:
        agent_type: 에이전트 유형 (예: "exercise", "food" 등)
        agent_instance: 에이전트 인스턴스
    """
    global agents
    agents[agent_type] = agent_instance
    logger.info(f"에이전트 '{agent_type}' 등록 완료: {type(agent_instance).__name__}") 