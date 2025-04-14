"""
응답 생성 모듈
에이전트 결과를 기반으로 최종 응답을 생성하는 기능을 제공합니다.
"""

import time
import traceback
import logging
import os
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langsmith.run_helpers import traceable

from supervisor_modules.utils.logger_setup import get_logger
from supervisor_modules.utils.qdrant_helper import get_user_insights, search_relevant_conversations
from common_prompts.prompts import AGENT_CONTEXT_PROMPT, QDRANT_INSIGHTS_PROMPT, QDRANT_SEARCH_PROMPT
from supervisor_modules.state.state_manager import SupervisorState

# 로거 설정
logger = get_logger(__name__)

# 최대 응답 길이 설정
MAX_RESPONSE_LENGTH = 8000

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

@traceable(name="generate_response_with_insights")
async def generate_response_with_insights(agent_results: List[Dict[str, Any]], state: Dict[str, Any], message: str, email: Optional[str] = None) -> str:
    """
    QDrant에서 가져온 사용자 인사이트를 활용하여 응답을 생성합니다.
    
    Args:
        agent_results: 에이전트 응답 결과 목록
        state: 현재 상태 정보
        message: 사용자 메시지
        email: 사용자 이메일
        
    Returns:
        str: 인사이트를 활용한 최종 응답
    """
    try:
        # 기본 검사
        if not agent_results or len(agent_results) == 0:
            logger.warning("에이전트 결과가 없습니다. 기본 응답을 생성합니다.")
            return "죄송합니다, 현재 질문에 대한 답변을 생성할 수 없습니다. 다시 질문해 주세요."
            
        # 이메일이 없는 경우 기본 응답 생성
        if not email:
            logger.info("사용자 이메일이 없습니다. 기본 응답 생성기를 사용합니다.")
            combined_response = combine_results_to_string(agent_results)
            return combined_response
            
        # 인사이트 정보 가져오기
        user_insights_data = await get_user_insights(email)
        
        # 에이전트 응답 합치기
        agent_combined_response = combine_results_to_string(agent_results)
        
        # 대화 내역 포맷팅
        chat_history = state.get("chat_history", [])
        formatted_history = format_chat_history(chat_history)
                
        # 모델 및 프롬프트 설정
        model = ChatOpenAI(
            model_name="gpt-4o",
            temperature=0.7
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", QDRANT_INSIGHTS_PROMPT),
            ("human", message)
        ])
        
        # 변수 설정
        variables = {
            "message": message,
            "user_insights": user_insights_data.get("user_insights", "특별한 인사이트 정보가 없습니다."),
            "recent_events": user_insights_data.get("recent_events", "최근 특별한 이벤트가 없습니다."),
            "user_persona": user_insights_data.get("user_persona", "사용자 페르소나 정보가 없습니다."),
            "chat_history": formatted_history,
            "agent_response": agent_combined_response
        }
        
        # 응답 생성
        chain = prompt | model
        response = await chain.ainvoke(variables)
        
        final_response = response.content
        if len(final_response) > MAX_RESPONSE_LENGTH:
            final_response = final_response[:MAX_RESPONSE_LENGTH] + "..."
            
        return final_response
        
    except Exception as e:
        logger.error(f"인사이트 기반 응답 생성 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        # 오류 발생 시 기본 응답으로 에이전트 결과 사용
        return combine_results_to_string(agent_results)

@traceable(name="generate_response_with_semantic_search")
async def generate_response_with_semantic_search(agent_results: List[Dict[str, Any]], state: Dict[str, Any], message: str, email: Optional[str] = None) -> str:
    """
    QDrant 의미 검색을 활용하여 관련 과거 대화를 포함한 응답을 생성합니다.
    
    Args:
        agent_results: 에이전트 응답 결과 목록
        state: 현재 상태 정보
        message: 사용자 메시지
        email: 사용자 이메일
        
    Returns:
        str: 의미 검색 결과를 활용한 최종 응답
    """
    try:
        # 기본 검사
        if not agent_results or len(agent_results) == 0:
            logger.warning("에이전트 결과가 없습니다. 기본 응답을 생성합니다.")
            return "죄송합니다, 현재 질문에 대한 답변을 생성할 수 없습니다. 다시 질문해 주세요."
            
        # 이메일이 없는 경우 기본 응답 생성
        if not email:
            logger.info("사용자 이메일이 없습니다. 기본 응답 생성기를 사용합니다.")
            combined_response = combine_results_to_string(agent_results)
            return combined_response
            
        # 관련 대화 검색
        relevant_conversations = await search_relevant_conversations(email, message)
        
        # 에이전트 응답 합치기
        agent_combined_response = combine_results_to_string(agent_results)
        
        # 대화 내역 포맷팅
        chat_history = state.get("chat_history", [])
        formatted_history = format_chat_history(chat_history)
                
        # 모델 및 프롬프트 설정
        model = ChatOpenAI(
            model_name="gpt-4o",
            temperature=0.7
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", QDRANT_SEARCH_PROMPT),
            ("human", message)
        ])
        
        # 변수 설정
        variables = {
            "message": message,
            "relevant_conversations": relevant_conversations,
            "chat_history": formatted_history,
            "agent_response": agent_combined_response
        }
        
        # 응답 생성
        chain = prompt | model
        response = await chain.ainvoke(variables)
        
        final_response = response.content
        if len(final_response) > MAX_RESPONSE_LENGTH:
            final_response = final_response[:MAX_RESPONSE_LENGTH] + "..."
            
        return final_response
        
    except Exception as e:
        logger.error(f"의미 검색 기반 응답 생성 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        # 오류 발생 시 기본 응답으로 에이전트 결과 사용
        return combine_results_to_string(agent_results)

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
    
    # 직접 "action_plan" 문자열이 반환되는 경우 처리
    if agent_result == "action_plan" or agent_result == "steps" or agent_result == "actions":
        return "운동 계획을 생성 중입니다. 추천 운동 루틴을 곧 안내해 드리겠습니다."
    
    if isinstance(agent_result, str):
        # 문자열이 'action_plan'이거나 'steps' 같은 중간 계획인 경우 대체 메시지 반환
        if agent_result in ["action_plan", "steps"]:
            return "운동 계획을 생성 중입니다. 추천 운동 루틴을 곧 안내해 드리겠습니다."
        return agent_result
    
    if isinstance(agent_result, dict):
        # exercise 에이전트 응답 처리
        if "type" in agent_result and agent_result["type"] == "exercise" and "response" in agent_result:
            # response가 "action_plan"인 경우 처리
            if agent_result["response"] == "action_plan" or agent_result["response"] == "steps" or agent_result["response"] == "actions":
                return "운동 계획을 생성 중입니다. 추천 운동 루틴을 곧 안내해 드리겠습니다."
            return agent_result["response"]
        
        # 특정 패턴 확인 - action_plan이나 steps 같은 중간 계획 데이터가 있는지 확인
        if "action_plan" in agent_result or "steps" in agent_result or "actions" in agent_result:
            if "final_response" in agent_result and agent_result["final_response"]:
                return agent_result["final_response"]
            if "result" in agent_result and agent_result["result"]:
                return agent_result["result"]
            return "운동 계획을 생성 중입니다. 추천 운동 루틴을 곧 안내해 드리겠습니다."
        
        # 가능한 키 목록 순서대로 시도
        for key in ["content", "response", "answer", "output", "text", "message", "final_response", "result"]:
            if key in agent_result and agent_result[key] is not None:
                if isinstance(agent_result[key], str):
                    # 키 값이 'action_plan'이나 'steps' 같은 중간 계획인 경우 건너뛰기
                    if agent_result[key] in ["action_plan", "steps", "actions"]:
                        continue
                    return agent_result[key]
                else:
                    return str(agent_result[key])
        
        # 알려진 키가 없는 경우 전체 딕셔너리 반환
        return str(agent_result)
    
    # 리스트인 경우 action_plan이나 단계 정보일 수 있음
    if isinstance(agent_result, list) and len(agent_result) > 0:
        # 리스트의 첫 번째 항목에 'description', 'tool', 'input' 필드가 있으면 action_plan으로 간주
        if isinstance(agent_result[0], dict) and all(k in agent_result[0] for k in ["description", "tool"]):
            return "운동 계획을 생성 중입니다. 추천 운동 루틴을 곧 안내해 드리겠습니다."
    
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

def combine_results_to_string(agent_results: List[Dict[str, Any]]) -> str:
    """
    에이전트 결과 목록을 단일 문자열로 결합합니다.
    
    Args:
        agent_results: 에이전트 응답 결과 목록
        
    Returns:
        str: 결합된 응답 문자열
    """
    if not agent_results:
        return "응답을 생성할 수 없습니다."
        
    if len(agent_results) == 1:
        # 단일 결과인 경우
        result = agent_results[0].get("result", {})
        if isinstance(result, dict) and "response" in result:
            return result["response"]
        if isinstance(result, str):
            return result
        return str(result)
    
    # 여러 결과가 있는 경우
    responses = []
    for result in agent_results:
        if "agent" in result and "result" in result:
            agent_name = result["agent"]
            content = None
            
            if isinstance(result["result"], dict) and "response" in result["result"]:
                content = result["result"]["response"]
            elif isinstance(result["result"], str):
                content = result["result"]
            else:
                content = str(result["result"])
                
            if content:
                responses.append(f"【{agent_name}】\n{content}")
    
    if not responses:
        return "응답을 생성할 수 없습니다."
        
    return "\n\n".join(responses)

def format_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    """
    채팅 내역을 포맷팅합니다.
    
    Args:
        chat_history: 채팅 내역 목록
        
    Returns:
        str: 포맷팅된 채팅 내역
    """
    if not chat_history:
        return ""
        
    formatted_history = ""
    # 최대 5개의 최신 메시지만 사용
    recent_history = chat_history[-5:] if len(chat_history) > 5 else chat_history
    
    for entry in recent_history:
        role = "사용자" if entry.get("role", "") == "user" else "AI"
        content = entry.get("content", "")
        formatted_history += f"{role}: {content}\n"
        
    return formatted_history 