"""
메시지 분류 노드
사용자 메시지를 분석하여 적절한 카테고리로 분류하고 각 에이전트별 메시지를 생성
"""

import logging
import traceback
import time
import json
import os
from typing import Dict, Any, List, Tuple, Optional
from supervisor.langgraph.state import GymGGunState
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from langgraph.prompts.message_classification import message_classification_prompt

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.routing.message_classifier')

# LLM 초기화
try:
    llm = ChatOpenAI(
        temperature=0.2,
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
    )
    logger.info("메시지 분류용 LLM 초기화 완료")
except Exception as e:
    logger.error(f"메시지 분류용 LLM 초기화 오류: {str(e)}")
    llm = None

def analyze_message_with_llm(message: str, llm: Optional[BaseChatModel] = None) -> Tuple[List[str], Dict[str, str]]:
    """
    LLM을 사용하여 메시지를 분석하고 카테고리와 에이전트별 메시지를 생성
    
    Args:
        message: 분석할 사용자 메시지
        llm: 사용할 LLM 모델
        
    Returns:
        Tuple[List[str], Dict[str, str]]: (카테고리 리스트, 에이전트별 메시지 딕셔너리)
    """
    try:
        if not llm:
            logger.warning("LLM이 초기화되지 않았습니다. 기본 메시지로 대체합니다.")
            return ["general"], {"general": message}
            
        # 프롬프트 템플릿을 사용하여 메시지 생성
        formatted_prompt = message_classification_prompt.format(message=message)
        
        # LLM 호출
        result = llm.invoke(formatted_prompt)
        
        # JSON 파싱
        try:
            parsed_result = json.loads(result)
            categories = parsed_result.get("categories", ["general"])
            messages = parsed_result.get("messages", {"general": message})
            
            # 로깅
            logger.info(f"메시지 분석 결과 - 카테고리: {categories}")
            logger.info(f"에이전트별 메시지: {messages}")
            
            return categories, messages
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM 응답 JSON 파싱 실패: {e}")
            logger.error(f"원본 응답: {result}")
            return ["general"], {"general": message}
            
    except Exception as e:
        logger.error(f"메시지 분석 중 오류 발생: {e}")
        return ["general"], {"general": message}

def classify_with_llm(message: str, llm: Optional[BaseChatModel] = None) -> List[str]:
    """
    LLM을 사용하여 메시지의 카테고리를 분류
    
    Args:
        message: 분류할 사용자 메시지
        llm: 사용할 LLM 모델
        
    Returns:
        List[str]: 분류된 카테고리 리스트
    """
    categories, _ = analyze_message_with_llm(message, llm)
    return categories

def classify_with_keywords(message: str) -> str:
    """키워드 기반 메시지 분류 (LLM 실패 시 백업 방법)"""
    logger.info("키워드 기반 분류 방법 사용 중...")
    
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
    
    logger.info(f"키워드 기반 분류 결과: {message_type}")
    return message_type

def message_classifier(state: Dict[str, Any], llm: Optional[BaseChatModel] = None) -> Dict[str, Any]:
    """
    메시지 분류 노드
    사용자 메시지를 분석하여 적절한 카테고리로 분류하고 각 에이전트별 메시지를 생성
    
    Args:
        state: 현재 상태
        llm: 사용할 LLM 모델
        
    Returns:
        Dict[str, Any]: 업데이트된 상태
    """
    start_time = time.time()
    
    try:
        message = state.get("message", "")
        
        # 메시지 분석 및 분류
        categories, agent_messages = analyze_message_with_llm(message, llm)
        
        # 여러 카테고리 처리
        if categories:
            # 첫 번째 카테고리를 주 카테고리로 설정
            primary_category = categories[0]
            
            # 상태 업데이트
            state["classified_type"] = primary_category
            state["agent_messages"] = agent_messages
            
            # 모든 카테고리 저장 (병렬 처리를 위해)
            state["all_categories"] = categories
            
            # 로깅
            logger.info(f"메시지 분류 완료 - 주 카테고리: {primary_category}, 모든 카테고리: {categories}")
        else:
            # 카테고리가 없는 경우 기본값 사용
            state["classified_type"] = "general"
            state["agent_messages"] = {"general": message}
            state["all_categories"] = ["general"]
            logger.info("카테고리를 찾지 못해 general로 설정")
        
        # 처리 시간 기록
        end_time = time.time()
        state["metrics"]["classification_time"] = end_time - start_time
        
        logger.info(f"에이전트별 메시지: {state['agent_messages']}")
        
        return state
        
    except Exception as e:
        logger.error(f"메시지 분류 중 오류 발생: {e}")
        state["error"] = str(e)
        state["classified_type"] = "general"
        state["agent_messages"] = {"general": state.get("message", "")}
        state["all_categories"] = ["general"]
        return state 