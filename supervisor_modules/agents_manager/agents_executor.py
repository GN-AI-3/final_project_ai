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
from typing import Dict, Any, List, Optional, Tuple
from contextlib import nullcontext

from langsmith.run_helpers import traceable

from supervisor_modules.state.state_manager import SupervisorState
from supervisor_modules.classification.classifier import classify_message
from supervisor_modules.utils.context_builder import build_agent_context, format_context_for_agent
from common_prompts.prompts import AGENT_CONTEXT_PROMPT

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
    email = state.email
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
        
        # 에이전트별 문맥 정보 구성
        if not hasattr(state, 'context_info') or not state.context_info:
            logger.info(f"[{request_id}] 에이전트 문맥 정보 구성 시작")
            context_info = await build_agent_context(
                message=message,
                categories=selected_agents,
                chat_history=chat_history,
                user_traits=state.context.get('user_traits')
            )
            state.context_info = context_info
            logger.info(f"[{request_id}] 에이전트 문맥 정보 구성 완료: {list(context_info.keys())}")
        else:
            logger.info(f"[{request_id}] 기존 문맥 정보 사용: {list(state.context_info.keys())}")
        
        # 병렬 실행을 위한 태스크 목록 생성
        agent_tasks = []
        agent_names = []
        
        for agent_name in selected_agents:
            if agent_name not in agents:
                logger.warning(f"[{request_id}] 에이전트 '{agent_name}' 찾을 수 없음")
                continue
                
            agent = agents[agent_name]
            logger.info(f"[{request_id}] 에이전트 '{agent_name}' 태스크 생성")
            
            # 에이전트 문맥 정보 가져오기
            agent_context = format_context_for_agent(state.context_info, agent_name)
            
            # 에이전트 실행 태스크 생성
            task = run_agent(request_id, agent_name, agent, message, chat_history, agent_context)
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

async def run_agent(request_id: str, agent_name: str, agent: Any, message: str, chat_history: List[Dict[str, Any]], context_info: str = "") -> Dict[str, Any]:
    """
    단일 에이전트 실행을 위한 헬퍼 함수
    
    Args:
        request_id: 요청 식별자
        agent_name: 에이전트 이름
        agent: 에이전트 인스턴스
        message: 사용자 메시지
        chat_history: 대화 내역
        context_info: 카테고리별 문맥 정보 (선택 사항)
        
    Returns:
        Dict[str, Any]: 에이전트 실행 결과
    """
    agent_start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 에이전트 '{agent_name}' 실행 중")
        
        if context_info:
            logger.info(f"[{request_id}] 에이전트 '{agent_name}'에 문맥 정보 전달: {context_info[:50]}...")
        
        # 에이전트 실행
        agent_result = await agent.process(
            message=message,
            chat_history=chat_history,
            context_info=context_info
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

async def process_message(message: str, email: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하고 적절한 에이전트에 라우팅합니다.
    
    Args:
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        context: 추가 컨텍스트 정보 (선택 사항)
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        logger.info(f"[{request_id}] 메시지 처리 시작: '{message[:50]}...' (email: {email})")
        
        # 컨텍스트 정보가 없는 경우 초기화
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            logger.warning(f"[{request_id}] context가 딕셔너리가 아닙니다({type(context)}). 빈 딕셔너리로 초기화합니다.")
            context = {}
            
        # SupervisorState 초기화
        state = SupervisorState(
            request_id=request_id,
            message=message,
            email=email,
            context=context
        )
        
        # 메시지 분류 - 새로운 시그니처 사용
        categories, metadata = await classify_message(message, context)
        
        # 상태 업데이트
        state.categories = categories
        state.selected_agents = categories  # 현재는 카테고리와 에이전트를 1:1로 매핑
        state.metrics["classification_time"] = metadata.get("classification_time", 0)
        state.metrics["classification_metadata"] = metadata
        
        # 문맥 정보 구성 (있으면 사용, 없으면 새로 생성)
        context_info = metadata.get("context_info", {})
        if not context_info:
            # user_traits는 context가 딕셔너리일 때만 추출
            user_traits = context.get('user_traits') if isinstance(context, dict) else None
            
            context_info = await build_agent_context(
                message=message,
                categories=categories,
                chat_history=state.chat_history,
                user_traits=user_traits
            )
        state.context_info = context_info
        
        # 에이전트 실행
        state_dict = state.to_dict()
        state_dict = await execute_agents(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 응답 생성
        from supervisor_modules.response.response_generator import generate_response
        response = await generate_response(state)
        
        # 최종 결과 생성
        result = {
            "request_id": request_id,
            "response": response,
            "categories": categories,
            "selected_agents": state.selected_agents,
            "agent_results": state.agent_results,
            "metrics": {
                "total_time": time.time() - start_time,
                "classification_time": state.metrics.get("classification_time", 0),
                "execution_time": state.metrics.get("execution_time", 0),
                "response_time": state.metrics.get("response_time", 0)
            }
        }
        
        logger.info(f"[{request_id}] 메시지 처리 완료 (소요시간: {result['metrics']['total_time']:.2f}초)")
        return result
        
    except Exception as e:
        logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "request_id": request_id if 'request_id' in locals() else str(uuid.uuid4()),
            "response": f"죄송합니다. 요청을 처리하는 중 오류가 발생했습니다: {str(e)}",
            "error": str(e)
        }

def register_agent(agent_type: str, agent_instance: Any) -> None:
    """
    에이전트를 전역 레지스트리에 등록합니다.
    
    Args:
        agent_type: 에이전트 타입 (exercise, food, schedule, motivation, general 등)
        agent_instance: 에이전트 인스턴스 (process 메서드를 가지고 있어야 함)
    """
    global agents
    agents[agent_type] = agent_instance
    logger.info(f"에이전트 '{agent_type}' 등록 완료")

def route_message(message: str, email: str = None, categories: List[str] = None) -> Dict[str, Any]:
    """에이전트 라우팅 및 응답 생성 (레거시 지원용)"""
    return asyncio.run(process_message(message, email, {"categories": categories} if categories else None)) 