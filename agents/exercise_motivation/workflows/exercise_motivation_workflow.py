"""
운동 동기부여 워크플로우 모듈

이 모듈은 사용자의 운동 패턴을 분석하고, 개인화된 동기부여 메시지를 생성하는 워크플로우를 정의합니다.
"""
import os
import logging
from typing import Dict, Any, List, Optional, Callable, TypedDict
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from agents.exercise_motivation.tools.db_tools import ExerciseDBTools
from agents.exercise_motivation.tools.schedule_tools import ScheduleTools
from agents.exercise_motivation.prompts.motivation_prompts import (
    get_motivation_prompt_template,
    get_pattern_details
)

# 로깅 설정
logger = logging.getLogger(__name__)

# 타입 정의
class MotivationState(TypedDict):
    """동기부여 워크플로우 상태를 정의하는 타입"""
    user_id: int
    records: List[Dict[str, Any]]
    pattern: str
    weeks: int
    attendance_rate: float
    memo_rate: float
    total_records: int
    message: Optional[str]

def process_user_data(user_id: int) -> MotivationState:
    """
    사용자 데이터를 처리하고 초기 상태를 생성합니다.
    
    Args:
        user_id: 사용자 ID
        
    Returns:
        MotivationState: 초기화된 워크플로우 상태
    """
    try:
        # 사용자 운동 기록 조회
        records = ExerciseDBTools.get_user_exercise_records(user_id)
        
        # 운동 패턴 분석
        pattern_data = ExerciseDBTools.get_exercise_pattern(records)
        pattern = pattern_data.get("pattern", "inactive")
        attendance_rate = pattern_data.get("attendance_rate", 0.0)
        total_records = pattern_data.get("total_records", 0)
        memo_rate = pattern_data.get("memo_rate", 0.0)
        
        # 운동 시작 후 주차 계산
        weeks = ExerciseDBTools.get_exercise_weeks(records)
        
        # 초기 상태 반환
        return {
            "user_id": user_id,
            "records": records,
            "pattern": pattern,
            "weeks": weeks,
            "attendance_rate": attendance_rate,
            "memo_rate": memo_rate,
            "total_records": total_records,
            "message": None
        }
        
    except Exception as e:
        logger.error(f"사용자 데이터 처리 중 오류: {str(e)}")
        # 오류 발생 시 기본 상태 반환
        return {
            "user_id": user_id,
            "records": [],
            "pattern": "inactive",
            "weeks": 1,
            "attendance_rate": 0.0,
            "memo_rate": 0.0,
            "total_records": 0,
            "message": None
        }

def generate_motivation_message(state: MotivationState, llm: Optional[ChatOpenAI] = None) -> MotivationState:
    """
    상태 정보를 기반으로 동기부여 메시지를 생성합니다.
    
    Args:
        state: 현재 워크플로우 상태
        llm: 언어 모델 (기본값: ChatOpenAI)
        
    Returns:
        MotivationState: 업데이트된 워크플로우 상태
    """
    try:
        # 언어 모델 초기화
        if llm is None:
            llm = ChatOpenAI(
                temperature=0.7,
                model=os.getenv("OPENAI_MODEL_NAME", "gpt-4-0125-preview")
            )
        
        # 운동 패턴 설명 생성
        pattern_details = get_pattern_details(
            state["pattern"], 
            state["attendance_rate"], 
            state["total_records"]
        )
        
        # 주차에 따른 프롬프트 템플릿 선택
        prompt_template = get_motivation_prompt_template(state["weeks"])
        
        # 프롬프트 변수 입력
        prompt_variables = {
            "weeks": state["weeks"],
            "pattern": state["pattern"],
            "pattern_details": pattern_details,
            "memo_rate": state["memo_rate"]
        }
        
        formatted_prompt = prompt_template.format_messages(**prompt_variables)
        
        # 언어 모델을 통한 동기부여 메시지 생성
        response = llm.invoke(formatted_prompt)
        motivation_message = response.content
        
        # 상태 업데이트
        updated_state = state.copy()
        updated_state["message"] = motivation_message
        
        logger.info(f"사용자 {state['user_id']}에 대한 동기부여 메시지 생성 완료")
        return updated_state
        
    except Exception as e:
        logger.error(f"동기부여 메시지 생성 중 오류: {str(e)}")
        # 오류 발생 시 기본 메시지로 상태 업데이트
        updated_state = state.copy()
        updated_state["message"] = "오늘도 운동을 통해 건강한 하루를 보내세요! 꾸준한 노력이 성공의 열쇠입니다. 💪"
        return updated_state

def save_and_schedule_message(state: MotivationState) -> MotivationState:
    """
    생성된 메시지를 저장하고 전송을 예약합니다.
    
    Args:
        state: 현재 워크플로우 상태
        
    Returns:
        MotivationState: 업데이트된 워크플로우 상태
    """
    try:
        if state["message"]:
            user_id = state["user_id"]
            weeks = state.get("weeks", 1)
            
            # DB에 메시지 저장
            ExerciseDBTools.save_motivation_message(user_id, state["message"])
            
            # 최적 전송 시간 계산 (주차에 따라 다른 전략 적용)
            # 1-2주차는 고정 시간, 3주차 이상은 사용자의 운동 시간 패턴에 맞춤
            if weeks <= 2:
                logger.info(f"사용자 {user_id}: 초기 단계로 기본 시간 사용 (오전 9시)")
                # 고정된 시간에 메시지 전송
                ScheduleTools.schedule_motivation_message(user_id, state["message"])
            else:
                # 운동 기록 조회 및 시간 패턴 분석
                records = state.get("records", [])
                time_analysis = ExerciseDBTools.analyze_exercise_time(records)
                
                preferred_time = time_analysis.get("preferred_time", "09:00")
                consistency = time_analysis.get("time_consistency", "low")
                
                logger.info(f"사용자 {user_id}: {weeks}주차, 선호 시간 {preferred_time}, 일관성 {consistency}")
                
                # 맞춤형 시간에 메시지 스케줄링
                ScheduleTools.schedule_motivation_message(user_id, state["message"])
            
            # 모바일 알람 설정 (옵션)
            ScheduleTools.set_mobile_alarm(user_id, state["message"])
            
            logger.info(f"사용자 {state['user_id']}의 동기부여 메시지 저장 및 스케줄링 완료")
            
        return state
        
    except Exception as e:
        logger.error(f"메시지 저장 및 스케줄링 중 오류: {str(e)}")
        return state

def create_exercise_motivation_workflow() -> Callable[[int], str]:
    """
    운동 동기부여 워크플로우를 생성합니다.
    
    Returns:
        Callable: 워크플로우 함수
    """
    llm = ChatOpenAI(
        temperature=0.7,
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-4-0125-preview")
    )
    
    def workflow(user_id: int) -> str:
        """
        사용자 ID를 입력받아 동기부여 메시지를 생성하는 워크플로우를 실행합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            str: 생성된 동기부여 메시지
        """
        try:
            # 1. 사용자 데이터 처리
            state = process_user_data(user_id)
            
            # 2. 동기부여 메시지 생성
            state = generate_motivation_message(state, llm)
            
            # 3. 메시지 저장 및 스케줄링
            state = save_and_schedule_message(state)
            
            return state["message"] or "오늘도 운동을 통해 건강한 하루를 보내세요!"
            
        except Exception as e:
            logger.error(f"워크플로우 실행 중 오류: {str(e)}")
            return "오늘도 운동을 통해 건강한 하루를 보내세요! 꾸준한 노력이 성공의 열쇠입니다. 💪"
    
    return workflow 