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
try:
    from supervisor_modules.utils.qdrant_helper import get_user_insights, search_relevant_conversations
except ImportError:
    # QDrant 기능이 없는 경우를 대비한 대체 함수
    async def get_user_insights(email: str) -> Dict[str, Any]:
        return {"user_insights": "", "recent_events": "", "user_persona": ""}
    
    async def search_relevant_conversations(email: str, query: str) -> List[Dict[str, Any]]:
        return []

from common_prompts.prompts import AGENT_CONTEXT_PROMPT, QDRANT_INSIGHTS_PROMPT, QDRANT_SEARCH_PROMPT
from supervisor_modules.state.state_manager import SupervisorState

# 로거 설정
logger = get_logger(__name__)

# 최대 응답 길이 설정
MAX_RESPONSE_LENGTH = 8000

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# LangSmith 트레이서 초기화
try:
    tracer = traceable(project_name=os.getenv("LANGCHAIN_PROJECT", "pr-only-praise-44"))
    logger.info(f"LangSmith 트레이서 초기화 성공 (프로젝트: {os.getenv('LANGCHAIN_PROJECT', 'pr-only-praise-44')})")
except Exception as e:
    logger.warning(f"LangSmith 트레이서 초기화 실패: {str(e)}")
    tracer = None

async def generate_response(state: SupervisorState) -> str:
    """
    에이전트 결과를 바탕으로 응답 생성
    
    Args:
        state: 현재 상태 객체
        
    Returns:
        str: 생성된 응답 텍스트
    """
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    message = state.message
    agent_results = state.agent_results
    selected_agents = state.selected_agents
    categories = state.categories
    context_info = getattr(state, 'context_info', {})
    
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
        
        return response
        
    except Exception as e:
        logger.error(f"[{request_id}] 응답 생성 과정에서 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 응답
        error_message = f"죄송합니다. 응답을 생성하는 과정에서 오류가 발생했습니다: {str(e)}"
        
        # 상태 업데이트
        state.response = error_message
        state.response_type = "error"
        state.metrics["response_generation_error"] = str(e)
        state.metrics["response_generation_time"] = time.time() - start_time
        
        return error_message

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
        try:
            user_insights_data = await get_user_insights(email)
        except Exception as e:
            logger.warning(f"인사이트 정보를 가져오는 중 오류 발생: {str(e)}. 기본 응답 생성기를 사용합니다.")
            combined_response = combine_results_to_string(agent_results)
            return combined_response
        
        # 에이전트 응답 합치기
        agent_combined_response = combine_results_to_string(agent_results)
        
        # 대화 내역 포맷팅
        chat_history = state.get("chat_history", [])
        formatted_history = format_chat_history(chat_history)
                
        # 모델 및 프롬프트 설정
        model = ChatOpenAI(
            model_name="gpt-3.5-turbo",
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
        str: 의미 검색 기반 최종 응답
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
        try:
            relevant_conversations = await search_relevant_conversations(email, message)
        except Exception as e:
            logger.warning(f"관련 대화 검색 중 오류 발생: {str(e)}. 기본 응답 생성기를 사용합니다.")
            combined_response = combine_results_to_string(agent_results)
            return combined_response
        
        # 관련 대화가 없는 경우 기본 응답 생성
        if not relevant_conversations:
            logger.info("관련 대화가 없습니다. 기본 응답 생성기를 사용합니다.")
            combined_response = combine_results_to_string(agent_results)
            return combined_response
            
        # 관련 대화 포맷팅
        formatted_conversations = ""
        for i, conv in enumerate(relevant_conversations[:3]):  # 최대 3개만 사용
            formatted_conversations += f"대화 {i+1}:\n"
            formatted_conversations += f"질문: {conv.get('question', '')}\n"
            formatted_conversations += f"답변: {conv.get('answer', '')}\n\n"
            
        # 에이전트 응답 합치기
        agent_combined_response = combine_results_to_string(agent_results)
        
        # 대화 내역 포맷팅
        chat_history = state.get("chat_history", [])
        formatted_history = format_chat_history(chat_history)
                
        # 모델 및 프롬프트 설정
        model = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.7
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", QDRANT_SEARCH_PROMPT),
            ("human", message)
        ])
        
        # 변수 설정
        variables = {
            "message": message,
            "relevant_conversations": formatted_conversations,
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
    에이전트 결과에서 응답 컨텐츠만 추출하는 헬퍼 함수
    
    Args:
        agent_result: 에이전트 응답 결과
        
    Returns:
        str: 추출된 응답 컨텐츠
    """
    # 이미 문자열인 경우
    if isinstance(agent_result, str):
        return agent_result
        
    # 딕셔너리인 경우 "response" 또는 "content" 키 찾기
    if isinstance(agent_result, dict):
        # "response" 키 확인
        if "response" in agent_result:
            response = agent_result["response"]
            if isinstance(response, str):
                return response
            elif isinstance(response, dict) and "content" in response:
                return response["content"]
                
        # "content" 키 확인
        if "content" in agent_result:
            return agent_result["content"]
            
        # "text" 키 확인
        if "text" in agent_result:
            return agent_result["text"]
            
        # "message" 키 확인
        if "message" in agent_result:
            return agent_result["message"]
            
        # 딕셔너리 값 중 첫 번째 문자열 반환
        for key, value in agent_result.items():
            if isinstance(value, str):
                return value
                
        # 모든 키-값 쌍을 문자열로 변환하여 반환
        contents = []
        for key, value in agent_result.items():
            contents.append(f"{key}: {value}")
        return "\n".join(contents)
        
    # 리스트인 경우
    if isinstance(agent_result, list):
        # 첫 번째 요소 확인
        if len(agent_result) > 0:
            return extract_agent_content(agent_result[0])
            
    # 다른 타입인 경우 문자열로 변환
    return str(agent_result)

def combine_agent_responses(valid_results: List[Dict[str, Any]], categories: List[str], request_id: str) -> str:
    """
    여러 에이전트 응답을 결합하는 함수
    
    Args:
        valid_results: 유효한 에이전트 결과 목록
        categories: 분류된 카테고리 목록
        request_id: 요청 식별자
        
    Returns:
        str: 결합된 응답
    """
    try:
        combined_responses = {}
        
        # 각 유효한 결과 처리
        for result in valid_results:
            agent_name = result.get("agent", "unknown")
            agent_content = extract_agent_content(result.get("result", ""))
            combined_responses[agent_name] = agent_content
            
        # 카테고리별로 결합
        if len(combined_responses) == 1:
            # 단일 응답만 있는 경우
            return next(iter(combined_responses.values()))
            
        # 여러 응답 결합
        final_response = ""
        for agent, response in combined_responses.items():
            if response:
                final_response += response + "\n\n"
                
        return final_response.strip()
        
    except Exception as e:
        logger.error(f"[{request_id}] 응답 결합 중 오류 발생: {str(e)}")
        
        # 오류 시 유효한 결과 중 첫 번째 응답 사용
        if valid_results and len(valid_results) > 0:
            return extract_agent_content(valid_results[0].get("result", ""))
            
        return "응답을 생성하는 중 오류가 발생했습니다."

def combine_results_to_string(agent_results: List[Dict[str, Any]]) -> str:
    """
    에이전트 결과 목록을 단일 문자열로 결합합니다.
    
    Args:
        agent_results: 에이전트 결과 목록
        
    Returns:
        str: 결합된 응답 문자열
    """
    if not agent_results:
        return "응답을 생성하는 중 오류가 발생했습니다."
    
    combined_text = ""
    for result in agent_results:
        if "error" in result:
            continue
        
        agent_type = result.get("agent", "unknown")
        agent_result = result.get("result", {})
        
        # 에이전트 결과 추출
        content = extract_agent_content(agent_result)
        if content:
            if combined_text:
                combined_text += "\n\n"
            combined_text += content
    
    # 결합된 텍스트가 없으면 기본 메시지 반환
    if not combined_text:
        return "죄송합니다, 현재 질문에 대한 답변을 생성할 수 없습니다. 다시 질문해 주세요."
    
    # 최대 길이 제한
    if len(combined_text) > MAX_RESPONSE_LENGTH:
        combined_text = combined_text[:MAX_RESPONSE_LENGTH] + "..."
        
    return combined_text

def format_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    """
    대화 내역을 형식화합니다.
    
    Args:
        chat_history: 대화 내역 목록
        
    Returns:
        str: 형식화된 대화 내역 문자열
    """
    if not chat_history:
        return ""
    
    formatted_history = ""
    
    # 최근 5개 대화만 사용
    recent_history = chat_history[-5:] if len(chat_history) > 5 else chat_history
    
    for entry in recent_history:
        role = "사용자" if entry.get("role", "") == "user" else "AI"
        content = entry.get("content", "")
        formatted_history += f"{role}: {content}\n"
    
    return formatted_history.strip() 