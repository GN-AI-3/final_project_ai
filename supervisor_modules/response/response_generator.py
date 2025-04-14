"""
응답 생성 모듈
에이전트 결과를 바탕으로 응답을 생성합니다.
"""

import time
import traceback
import logging
import os
from typing import Dict, Any, List
from contextlib import nullcontext

from langsmith.run_helpers import traceable

from supervisor_modules.state.state_manager import SupervisorState

# 로거 설정
logger = logging.getLogger(__name__)

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "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")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "pr-only-praise-44")

# LangSmith 트레이서 초기화
try:
    tracer = traceable(project_name=os.getenv("LANGCHAIN_PROJECT", "pr-only-praise-44"))
    logger.info(f"LangSmith 트레이서 초기화 성공 (프로젝트: {os.getenv('LANGCHAIN_PROJECT', 'pr-only-praise-44')})")
except Exception as e:
    logger.warning(f"LangSmith 트레이서 초기화 실패: {str(e)}")
    tracer = None

# 최대 응답 길이 설정
MAX_RESPONSE_LENGTH = 8000

async def generate_response(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    에이전트 결과를 바탕으로 응답 생성
    
    Args:
        state_dict: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    agent_results = state.agent_results
    selected_agents = state.selected_agents
    categories = state.categories
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 응답 생성 시작 - 에이전트 결과 {len(agent_results)}개")
        
        # LangSmith 런 이름 설정
        run_name = f"응답 생성: {request_id}"
        
        # LangSmith 트레이서를 사용한 응답 생성
        with tracer.new_trace(name=run_name, run_type="chain") if tracer else nullcontext():
            if not agent_results:
                raise ValueError("에이전트 결과가 없습니다.")
            
            # 유효한 결과만 추출
            valid_results = []
            for result in agent_results:
                if "error" not in result:
                    valid_results.append(result)
            
            if not valid_results:
                raise ValueError("유효한 에이전트 결과가 없습니다.")
            
            logger.info(f"[{request_id}] 유효한 에이전트 결과 {len(valid_results)}개")
            
            # 응답 결합
            if len(valid_results) == 1:
                # 단일 에이전트 결과
                combined_result = extract_agent_content(valid_results[0]["result"])
                logger.info(f"[{request_id}] 단일 에이전트 응답 사용")
            else:
                # 여러 에이전트 결과 결합
                combined_result = combine_agent_responses(valid_results, categories, request_id)
                logger.info(f"[{request_id}] 다중 에이전트 응답 결합")
            
            # 응답 형식화
            response = combined_result
            if len(response) > MAX_RESPONSE_LENGTH:
                response = response[:MAX_RESPONSE_LENGTH] + "..."
        
        # 상태 업데이트
        state.response = response
        state.response_type = "text"  # 기본 응답 타입
        state.metrics["response_generation_time"] = time.time() - start_time
        
        logger.info(f"[{request_id}] 응답 생성 완료 (소요시간: {time.time() - start_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"[{request_id}] 응답 생성 과정에서 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 응답과 함께 상태 업데이트
        state.response = f"죄송합니다. 응답을 생성하는 과정에서 오류가 발생했습니다: {str(e)}"
        state.response_type = "error"
        state.metrics["response_generation_error"] = str(e)
        state.metrics["response_generation_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict()

def extract_agent_content(agent_result: Any) -> str:
    """
    에이전트 결과에서 내용 추출
    
    Args:
        agent_result: 에이전트 결과
        
    Returns:
        str: 추출된 내용
    """
    if agent_result is None:
        return "응답이 없습니다."
    
    if isinstance(agent_result, str):
        return agent_result
    
    if isinstance(agent_result, dict):
        # 가능한 키 목록 순서대로 시도
        for key in ["content", "response", "answer", "output", "text", "message"]:
            if key in agent_result and agent_result[key] is not None:
                if isinstance(agent_result[key], str):
                    return agent_result[key]
                else:
                    return str(agent_result[key])
        
        # 알려진 키가 없는 경우 전체 딕셔너리 반환
        return str(agent_result)
    
    # 기타 타입
    return str(agent_result)

def combine_agent_responses(valid_results: List[Dict[str, Any]], categories: List[str], request_id: str) -> str:
    """
    여러 에이전트의 응답을 결합
    
    Args:
        valid_results: 유효한 에이전트 결과 목록
        categories: 분류된 카테고리 목록
        request_id: 요청 식별자
        
    Returns:
        str: 결합된 응답
    """
    # 카테고리별 결과 추출
    category_results = {}
    for result in valid_results:
        agent_name = result["agent"]
        content = extract_agent_content(result["result"])
        category_results[agent_name] = content
    
    # 특별한 케이스 처리
    if "exercise" in category_results and "food" in category_results:
        # 운동과 식단 결합
        exercise_content = category_results["exercise"]
        food_content = category_results["food"]
        
        combined = "【운동 관련】\n" + exercise_content + "\n\n【식단 관련】\n" + food_content
        logger.info(f"[{request_id}] 운동과 식단 결과 결합")
        return combined
    
    # 일반적인 결과 결합 (첫 번째 에이전트의 결과 사용)
    priority_order = ["motivation", "exercise", "food", "schedule", "general"]
    
    for category in priority_order:
        if category in category_results:
            logger.info(f"[{request_id}] 우선순위에 따라 '{category}' 에이전트 응답 선택")
            return category_results[category]
    
    # 우선순위에 없는 경우 첫 번째 결과 반환
    first_agent = list(category_results.keys())[0]
    logger.info(f"[{request_id}] 우선순위에 없는 에이전트 - 첫 번째 '{first_agent}' 응답 선택")
    return category_results[first_agent] 