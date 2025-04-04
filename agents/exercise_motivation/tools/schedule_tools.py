"""
운동 동기부여 에이전트의 스케줄 관련 도구 모듈
"""
import os
import logging
import requests
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional

from agents.exercise_motivation.tools.db_tools import ExerciseDBTools

# 로깅 설정
logger = logging.getLogger(__name__)

class ScheduleTools:
    """스케줄링 관련 도구"""
    
    # 기본 메시지 전송 시간
    DEFAULT_SEND_TIME = "09:00"  # 오전 9시
    
    @staticmethod
    def get_optimal_send_time(user_id: int, weeks: int) -> str:
        """
        최적의 메시지 전송 시간을 계산합니다.
        주차에 따라 다른 전략 적용 (1-2주차는 고정 시간, 3주차 이상은 사용자 맞춤)
        
        Args:
            user_id: 사용자 ID
            weeks: 운동 시작 후 주차
            
        Returns:
            str: 최적 전송 시간 (HH:MM 형식)
        """
        # 1-2주차는 기본 시간 사용
        if weeks <= 2:
            logger.info(f"사용자 {user_id}: 초기 단계로 기본 시간 사용 ({ScheduleTools.DEFAULT_SEND_TIME})")
            return ScheduleTools.DEFAULT_SEND_TIME
            
        # 3주차 이상은 사용자의 운동 패턴 분석
        try:
            # 운동 기록 조회
            records = ExerciseDBTools.get_user_exercise_records(user_id)
            
            # 운동 시간 분석
            time_analysis = ExerciseDBTools.analyze_exercise_time(records)
            preferred_time = time_analysis.get("preferred_time", ScheduleTools.DEFAULT_SEND_TIME)
            
            # 시간 일관성에 따른 처리
            consistency = time_analysis.get("time_consistency", "low")
            
            if consistency == "high":
                # 일관성이 높으면 그대로 사용
                send_time = preferred_time
                logger.info(f"사용자 {user_id}: 높은 시간 일관성, 선호 시간 사용 ({send_time})")
            elif consistency == "medium":
                # 일관성이 중간이면 30분 전에 알림
                hour, minute = map(int, preferred_time.split(":"))
                dt = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M")
                dt_adjusted = dt - timedelta(minutes=30)
                send_time = dt_adjusted.strftime("%H:%M")
                logger.info(f"사용자 {user_id}: 중간 시간 일관성, 30분 전 알림 ({send_time})")
            else:
                # 일관성이 낮으면 아침에 전송
                send_time = "08:00"
                logger.info(f"사용자 {user_id}: 낮은 시간 일관성, 아침 시간 사용 ({send_time})")
                
            return send_time
            
        except Exception as e:
            logger.error(f"최적 전송 시간 계산 중 오류: {str(e)}")
            return ScheduleTools.DEFAULT_SEND_TIME
    
    @staticmethod
    def schedule_motivation_message(user_id: int, message: str) -> bool:
        """
        동기부여 메시지 전송을 예약합니다.
        
        Args:
            user_id: 사용자 ID
            message: 동기부여 메시지
            
        Returns:
            bool: 예약 성공 여부
        """
        try:
            # 사용자 운동 기록 조회 및 주차 계산
            records = ExerciseDBTools.get_user_exercise_records(user_id)
            weeks = ExerciseDBTools.get_exercise_weeks(records)
            
            # 최적 전송 시간 계산
            send_time = ScheduleTools.get_optimal_send_time(user_id, weeks)
            
            # 현재 날짜에 전송 시간 적용
            current_date = datetime.now().strftime('%Y-%m-%d')
            scheduled_time = f"{current_date} {send_time}"
            
            # 스케줄링 로직 (실제로는 외부 서비스나 스케줄러 사용)
            logger.info(f"사용자 {user_id}에 대한 동기부여 메시지 {scheduled_time}에 전송 예약")
            
            return True
            
        except Exception as e:
            logger.error(f"메시지 스케줄링 중 오류: {str(e)}")
            return False
    
    @staticmethod
    def set_mobile_alarm(user_id: int, message: str) -> bool:
        """
        모바일 앱 알림을 설정합니다.
        
        Args:
            user_id: 사용자 ID
            message: 알림 메시지
            
        Returns:
            bool: 알림 설정 성공 여부
        """
        try:
            # 사용자 운동 기록 조회 및 주차 계산
            records = ExerciseDBTools.get_user_exercise_records(user_id)
            weeks = ExerciseDBTools.get_exercise_weeks(records)
            
            # 최적 전송 시간 계산
            send_time = ScheduleTools.get_optimal_send_time(user_id, weeks)
            
            # 모바일 앱 알림 설정 로직 (실제로는 FCM 등 사용)
            shortened_message = message[:50] + "..." if len(message) > 50 else message
            logger.info(f"사용자 {user_id}에 대한 모바일 알림 {send_time}에 예약: {shortened_message}")
            
            return True
            
        except Exception as e:
            logger.error(f"모바일 알림 설정 중 오류: {str(e)}")
            return False 