"""
분류 모듈
메시지 분류 기능을 제공합니다.
"""

import time
import json
import traceback
import os
import logging
from typing import Dict, Any, List
from contextlib import nullcontext

import openai
from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage
from langsmith.run_helpers import traceable

# 로그 설정
logging.basicConfig(level=logging.INFO)

from supervisor_modules.state.state_manager import SupervisorState

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# 로거 설정
logger = logging.getLogger(__name__)

# LangSmith 트레이서 초기화
try:
    tracer = traceable(project_name=os.getenv("LANGCHAIN_PROJECT"))
    logger.info(f"LangSmith 트레이서 초기화 성공 (프로젝트: {os.getenv('LANGCHAIN_PROJECT')})")
except Exception as e:
    logger.warning(f"LangSmith 트레이서 초기화 실패: {str(e)}")
    tracer = None

# 카테고리 분류를 위한 시스템 프롬프트
CATEGORY_SYSTEM_PROMPT = """당신은 사용자의 메시지를 분석하고 적절한 카테고리로 분류하는 도우미입니다.
사용자의 메시지를 다음 카테고리 중 적합한 카테고리를 모두 찾아서 분류해야 합니다:

1. exercise: 운동, 피트니스, 트레이닝, 근육, 스트레칭, 체력, 운동 루틴, 운동 계획, 운동 방법, 요일별 운동 추천, 운동 일정 계획, 운동 프로그램 등에 관련된 질문
2. food: 음식, 식단, 영양, 요리, 식품, 건강식, 식이요법, 다이어트 식단, 영양소 등에 관련된 질문
3. schedule: PT 예약, 트레이닝 세션 일정, 코치 미팅 스케줄, 피트니스 클래스 등록, 헬스장 방문 일정 등 실제 일정 관리에 관련된 질문
4. motivation: 동기 부여, 의지 강화, 습관 형성, 마음가짐, 목표 설정 등에 관련된 질문
5. general: 위 카테고리에 명확하게 속하지 않지만 건강/피트니스와 관련된 일반 대화

분류 시 주의사항:
- 운동 루틴이나 운동 계획, 요일별 운동 추천, 주간 운동 계획 등은 모두 schedule이 아닌 exercise 카테고리로 분류하세요.
- 요일별 식단이나 식단 계획은 food 카테고리로 분류하세요.
- schedule 카테고리는 실제 PT 예약, 코치 미팅, 피트니스 클래스 참여와 같은 구체적인 일정 관리에만 사용하세요.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천해줘"와 같은 질문은 exercise 카테고리입니다.
- "이번주 월,수,금에 운동할건데 식단 추천해줘"와 같은 질문은 food 카테고리입니다.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천이랑 식단 같이 짜줘"와 같은 질문은 exercise와 food 카테고리입니다.

제공된 사용자 메시지를 분석하고 관련된 모든 카테고리를 JSON 배열 형식으로 반환하세요.
예: ["exercise", "food"], ["food"], ["motivation"]

사용자 메시지가 여러 카테고리에 해당할 수 있으며, 최대 3개까지의 관련 카테고리를 반환하세요.
동시에 여러 주제를 언급한 경우, 관련된 모든 카테고리를 포함해야 합니다.
예를 들어, "운동과 식단 계획을 알려줘"는 ["exercise", "food"]와 같이 분류될 수 있습니다."""

@traceable(run_type="chain", name="메시지 분류")
def classify_message(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 메시지를 분류하여 적절한 에이전트 카테고리를 할당합니다.
    
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
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 메시지 분류 시작: '{message[:50]}...'")
        
        # LangChain 모델로 변경하여 LangSmith에 로깅
        try:
            # 모델 초기화
            chat_model = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.1
            )
            
            # LangSmith 로깅을 위한 모델 호출
            messages = [
                SystemMessage(content=CATEGORY_SYSTEM_PROMPT),
                HumanMessage(content=message)
            ]
            
            # 모델 호출
            response = chat_model.invoke(messages)
            
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
                
        except Exception as api_e:
            # API 호출 실패 시 기본 카테고리로 "general" 사용
            logger.error(f"[{request_id}] OpenAI API 호출 오류: {str(api_e)}, 기본 카테고리 'general' 사용")
            state.categories = ["general"]
            state.selected_agents = ["general"]
        
        # 메트릭 기록
        state.metrics["classification_time"] = time.time() - start_time
        logger.info(f"[{request_id}] 메시지 분류 완료: {state.categories} (소요시간: {time.time() - start_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 분류 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 카테고리 사용
        state.categories = ["general"]
        state.selected_agents = ["general"]
        state.metrics["classification_error"] = str(e)
        state.metrics["classification_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict() 