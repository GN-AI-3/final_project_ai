"""
개인화된 운동 동기부여 에이전트 모델
"""
import os
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from agents.exercise_motivation.tools.db_tools import ExerciseDBTools
from agents.exercise_motivation.tools.schedule_tools import ScheduleTools
from agents.exercise_motivation.prompts.motivation_prompts import (
    get_motivation_prompt_template,
    get_pattern_details
)

# 로깅 설정
logger = logging.getLogger(__name__)

class ExerciseMotivationAgent(BaseAgent):
    """개인화된 운동 동기부여 메시지를 생성하는 에이전트"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        ExerciseMotivationAgent 초기화
        
        Args:
            llm: 사용할 언어 모델 (기본값: ChatOpenAI)
        """
        # 언어 모델 초기화
        self.llm = llm or ChatOpenAI(
            temperature=0.7,
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4-0125-preview")
        )
        super().__init__(model=self.llm)
    
    def generate_motivation_message(self, user_id: int, current_text: str = None) -> str:
        """
        사용자의 운동 패턴을 분석하고 맞춤형 동기부여 메시지를 생성합니다.
        
        Args:
            user_id: 사용자 ID
            current_text: 현재 대화 텍스트 (미사용)
            
        Returns:
            str: 생성된 동기부여 메시지
        """
        try:
            # 1. 사용자 운동 기록 조회
            records = ExerciseDBTools.get_user_exercise_records(user_id)
            
            # 2. 운동 패턴 분석
            pattern_data = ExerciseDBTools.get_exercise_pattern(records)
            pattern = pattern_data.get("pattern")
            total_records = pattern_data.get("total_records")
            memo_rate = pattern_data.get("memo_rate")
            
            # 3. 운동 시작 후 주차 계산
            weeks = ExerciseDBTools.get_exercise_weeks(records)
            
            # 4. 운동 패턴 설명 생성
            pattern_details = get_pattern_details(pattern, memo_rate, total_records)
            
            # 5. 주차에 따른 프롬프트 템플릿 선택
            prompt_template = get_motivation_prompt_template(weeks)
            
            # 6. 프롬프트 변수 입력
            prompt_variables = {
                "weeks": weeks,
                "pattern": pattern,
                "pattern_details": pattern_details,
                "memo_rate": memo_rate
            }
            
            formatted_prompt = prompt_template.format_messages(**prompt_variables)
            
            # 7. 언어 모델을 통한 동기부여 메시지 생성
            response = self.llm.invoke(formatted_prompt)
            motivation_message = response.content
            
            # 8. DB에 메시지 저장
            ExerciseDBTools.save_motivation_message(user_id, motivation_message)
            
            logger.info(f"사용자 {user_id}에 대한 동기부여 메시지 생성 완료 (주차: {weeks}, 패턴: {pattern})")
            return motivation_message
            
        except Exception as e:
            logger.error(f"동기부여 메시지 생성 중 오류: {str(e)}")
            # 오류 발생 시 기본 메시지 반환
            return "오늘도 운동을 통해 건강한 하루를 보내세요! 꾸준한 노력이 성공의 열쇠입니다. 💪"
    
    def schedule_motivation_message(self, user_id: int) -> bool:
        """
        동기부여 메시지 전송을 예약합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            bool: 예약 성공 여부
        """
        try:
            # 사용자 운동 기록 조회
            records = ExerciseDBTools.get_user_exercise_records(user_id)
            
            # 운동 시작 후 주차 계산
            weeks = ExerciseDBTools.get_exercise_weeks(records)
            
            # 동기부여 메시지 생성
            message = self.generate_motivation_message(user_id)
            
            # 메시지 전송 스케줄링 (주차에 따라 다른 방식 적용)
            if weeks <= 2:
                # 1-2주차는 항상 같은 시간에 메시지 전송
                logger.info(f"사용자 {user_id}: 초기 단계({weeks}주차)로 기본 시간에 메시지 예약")
                success = ScheduleTools.schedule_motivation_message(user_id, message)
            else:
                # 3주차 이상은 사용자의 운동 시간대에 맞춰 메시지 전송
                time_analysis = ExerciseDBTools.analyze_exercise_time(records)
                preferred_time = time_analysis.get("preferred_time", "09:00")
                
                logger.info(f"사용자 {user_id}: {weeks}주차, 맞춤형 시간({preferred_time})에 메시지 예약")
                success = ScheduleTools.schedule_motivation_message(user_id, message)
            
            # 모바일 알람 설정
            if success:
                ScheduleTools.set_mobile_alarm(user_id, message)
                
            return success
            
        except Exception as e:
            logger.error(f"동기부여 메시지 스케줄링 중 오류: {str(e)}")
            return False
    
    def _process_message(self, message: str, **kwargs) -> str:
        """
        사용자 메시지를 처리하고 응답합니다. BaseAgent에서 상속
        
        Args:
            message: 사용자 메시지
            kwargs: 추가 매개변수
            
        Returns:
            str: 응답 메시지
        """
        user_id = kwargs.get("user_id", 1)  # 기본 사용자 ID는 1
        
        # 'schedule' 명령어 인식
        if "schedule" in message.lower() or "예약" in message:
            success = self.schedule_motivation_message(user_id)
            
            if success:
                return "동기부여 메시지가 성공적으로 예약되었습니다. 지정된 시간에 메시지를 받게 됩니다."
            else:
                return "메시지 예약 중 오류가 발생했습니다. 나중에 다시 시도해주세요."
        
        # 일반 동기부여 메시지 생성
        return self.generate_motivation_message(user_id, message) 