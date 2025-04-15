"""
분류 모듈
메시지 분류 기능을 제공합니다.
"""

import time
import json
import traceback
import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from contextlib import nullcontext
import re

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

# 후속 질문 감지 함수 추가
def detect_follow_up_question(message: str, chat_history: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    사용자 메시지가 이전 대화의 후속 질문인지 감지합니다.
    
    Args:
        message: 사용자 메시지
        chat_history: 대화 내역
        
    Returns:
        Tuple[bool, Optional[str]]: (후속 질문 여부, 이전 에이전트 타입)
    """
    # 대화 내역이 충분하지 않으면 후속 질문이 아님
    if not chat_history or len(chat_history) < 2:
        return False, None
    
    follow_up_detected = False
    previous_agent = None
    last_ai_message = None
    
    # 마지막 AI 응답 가져오기
    for entry in reversed(chat_history):
        if entry.get("role") == "assistant":
            last_ai_message = entry.get("content", "")
            # agent_type 정보 우선 확인
            if entry.get("agent_type"):
                previous_agent = entry.get("agent_type")
                break
    
    # 마지막으로 사용된 에이전트 타입 찾기 (agent_type이 없는 경우)
    if not previous_agent:
        for entry in reversed(chat_history):
            if entry.get("role") == "assistant" and entry.get("agent_type"):
                previous_agent = entry.get("agent_type")
                break
            # agent_type이 없는 경우 content 내용 분석하여 추론
            elif entry.get("role") == "assistant" and entry.get("content"):
                content = entry.get("content", "")
                if any(key in content.lower() for key in ["운동", "트레이닝", "근육", "피트니스", "스트레칭", "벤치"]):
                    previous_agent = "exercise"
                    break
                elif any(key in content.lower() for key in ["식단", "음식", "영양", "칼로리", "다이어트"]):
                    previous_agent = "food"
                    break
                elif any(key in content.lower() for key in ["일정", "예약", "스케줄", "시간"]):
                    previous_agent = "schedule"
                    break
                elif any(key in content.lower() for key in ["동기", "의지", "목표", "습관"]):
                    previous_agent = "motivation"
                    break
    
    # 향상된 후속 질문 감지 로직
    if last_ai_message:
        # 1. 메시지 길이 검사 (짧은 질문은 후속 질문일 가능성이 높음)
        short_query = len(message.strip()) <= 20
        
        # 2. 숫자 언급 검사 (목록의 항목을 참조할 가능성)
        number_mentions = any(char.isdigit() for char in message) or any(word in message for word in ["번째", "번", "첫", "두", "세", "네", "다섯"])
        
        # 3. 대명사 사용 감지 (이전 대화를 참조하는 지시대명사 포함)
        pronouns_detected = any(pron in message for pron in ["그거", "그것", "이것", "저것", "그", "이", "저"])
        
        # 4. 문맥 의존성 평가 (독립적인 질문인지 파악)
        context_dependent = False
        
        # 5. 기존 답변에 번호 목록이 있는지 확인 (1., 2., 3. 등)
        number_list_in_response = re.search(r"\d+\.\s", last_ai_message) is not None
        
        # 질문이나 요청이 단독으로 이해하기 어려운 경우
        if "?" in message or "어떻게" in message or "무엇" in message or "설명" in message or "알려" in message:
            # 질문이 단독으로 완전한지 평가
            # 주어나 목적어가 생략된 경우 문맥 의존적일 가능성이 높음
            subject_missing = not any(subj in message for subj in ["운동", "식단", "계획", "일정", "정보"])
            if subject_missing:
                context_dependent = True
        
        # 6. 종합 평가
        if ((short_query and (number_mentions or pronouns_detected)) or 
             context_dependent or 
             (number_mentions and number_list_in_response)):
            follow_up_detected = True
            
            # 숫자가 언급되고 이전 응답에 번호 목록이 있으면 이전 에이전트 사용 강화
            if number_mentions and number_list_in_response and not previous_agent:
                # 응답 내용 기반으로 에이전트 타입 추론
                if any(key in last_ai_message.lower() for key in ["운동", "트레이닝", "근육", "피트니스", "스트레칭", "벤치"]):
                    previous_agent = "exercise"
                elif any(key in last_ai_message.lower() for key in ["식단", "음식", "영양", "칼로리", "다이어트"]):
                    previous_agent = "food"
                elif any(key in last_ai_message.lower() for key in ["일정", "예약", "스케줄", "시간"]):
                    previous_agent = "schedule"
                elif any(key in last_ai_message.lower() for key in ["동기", "의지", "목표", "습관"]):
                    previous_agent = "motivation"
                else:
                    previous_agent = "general"
    
    return follow_up_detected, previous_agent

@traceable(run_type="chain", name="메시지 분류")
async def classify_message(message: str, context: Optional[Dict[str, Any]] = None) -> Tuple[List[str], Dict[str, Any]]:
    """
    사용자 메시지를 분류하여 적절한 에이전트 카테고리를 할당합니다.
    이전 대화 내역을 고려하여 분류합니다.
    
    Args:
        message: 사용자 메시지
        context: 컨텍스트 정보 (선택 사항)
        
    Returns:
        Tuple[List[str], Dict[str, Any]]: 카테고리 목록과 메타데이터 딕셔너리
    """
    start_time = time.time()
    # 임의의 요청 ID 생성
    request_id = ""
    email = None
    
    try:
        # 컨텍스트 타입 확인 및 변환
        if context is None:
            context = {}
        elif isinstance(context, list):
            # 리스트인 경우 빈 딕셔너리로 변환
            logger.warning(f"context가 리스트 형식으로 전달되었습니다. 빈 딕셔너리로 변환합니다.")
            context = {}
        elif not isinstance(context, dict):
            # 딕셔너리가 아닌 경우 변환 시도
            logger.warning(f"context가 예상치 못한 형식({type(context)})입니다. 빈 딕셔너리로 변환합니다.")
            context = {}
        
        # 컨텍스트에서 정보 추출
        request_id = str(context.get("request_id", ""))
        email = context.get("email")
        
        logger.info(f"[{request_id}] 메시지 분류 시작: '{message[:50]}...'")
        
        # 이전 대화 내역 가져오기
        chat_history = context.get("chat_history", [])
        
        if not chat_history and email:
            # 이메일로 대화 내역 가져오기
            try:
                chat_history = chat_history_manager.get_recent_messages(email, 10)
            except Exception as e:
                logger.warning(f"[{request_id}] 대화 내역 가져오기 실패: {str(e)}")
        
        # 먼저 후속 질문인지 확인
        follow_up_detected, previous_agent = detect_follow_up_question(message, chat_history)
        
        # 메타데이터 초기화
        metadata = {
            "classification_time": 0,
            "model": "gpt-3.5-turbo",
            "explanation": "",
            "follow_up_detected": follow_up_detected,
            "previous_agent": previous_agent
        }
        
        # 후속 질문이고 이전 에이전트가 있는 경우, 기존 에이전트 재사용
        if follow_up_detected and previous_agent:
            logger.info(f"[{request_id}] 후속 질문 감지: '{message}', 이전 에이전트: {previous_agent}")
            return [previous_agent], metadata
        
        # 대화 내역 포맷팅
        formatted_history = ""
        if chat_history:
            for entry in chat_history[-10:]:  # 최근 10개 메시지만 사용
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
            HumanMessage(content=f"{message}\n\n이전 대화:\n{formatted_history}" if formatted_history else message)
        ]
        
        # 모델 호출
        response = chat_model.invoke(messages)
        
        # 결과 파싱
        response_text = response.content.strip()
        logger.info(f"LLM 분류 응답: {response_text}")
        
        # 분류 시간 기록
        metadata["classification_time"] = time.time() - start_time
        
        try:
            # JSON 배열 파싱
            if "[" in response_text and "]" in response_text:
                # 배열 형식 추출
                json_start = response_text.find("[")
                json_end = response_text.rfind("]") + 1
                json_text = response_text[json_start:json_end]
                categories = json.loads(json_text)
                
                # 설명 추출 (있는 경우)
                explanation_start = response_text.rfind("]") + 1
                if explanation_start < len(response_text):
                    metadata["explanation"] = response_text[explanation_start:].strip()
            else:
                # JSON 객체 형식일 수 있음
                response_data = json.loads(response_text)
                if isinstance(response_data, dict) and "categories" in response_data:
                    categories = response_data["categories"]
                    if "explanation" in response_data:
                        metadata["explanation"] = response_data["explanation"]
                else:
                    categories = response_data
            
            # 리스트가 아닌 경우 처리
            if not isinstance(categories, list):
                categories = [categories]
            
            # 유효한 카테고리 목록
            valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
            
            # 유효한 카테고리만 필터링
            filtered_categories = [cat for cat in categories if cat in valid_categories]
            
            # 카테고리 수 제한 (최대 3개)
            if len(filtered_categories) > 3:
                filtered_categories = filtered_categories[:3]
            
            # 카테고리가 없으면 기본값 사용
            if not filtered_categories:
                filtered_categories = ["general"]
                metadata["backup_method"] = "default_category"
                logger.warning(f"[{request_id}] 유효한 카테고리가 없어 'general'로 기본 설정")
            
            logger.info(f"[{request_id}] LLM 메시지 분류 완료: {filtered_categories}")
            
        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 기본 카테고리로 "general" 사용
            logger.warning(f"[{request_id}] JSON 파싱 실패: {response_text}, 기본 카테고리 'general' 사용")
            filtered_categories = ["general"]
            metadata["error"] = f"JSON 파싱 오류: {str(e)}"
            metadata["backup_method"] = "json_parse_error"
            
        except Exception as e:
            # 기타 오류 처리
            logger.error(f"[{request_id}] 분류 결과 처리 중 오류: {str(e)}")
            filtered_categories = ["general"]
            metadata["error"] = f"분류 처리 오류: {str(e)}"
            metadata["backup_method"] = "processing_error"
            
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 분류 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 카테고리 사용
        filtered_categories = ["general"]
        metadata = {
            "classification_time": time.time() - start_time,
            "error": str(e),
            "backup_method": "exception"
        }
    
    # 최종 시간 기록
    metadata["classification_time"] = time.time() - start_time
    logger.info(f"[{request_id}] 메시지 분류 완료: {filtered_categories} (소요시간: {metadata['classification_time']:.2f}초)")
    
    # 결과 반환
    return filtered_categories, metadata 