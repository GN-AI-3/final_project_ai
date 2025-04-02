"""
헬스장 출석률 알림 시스템 패키지
"""

# 패키지 버전 정보
__version__ = "1.0.0"
__author__ = "헬스장 출석률 알림 개발팀"
__description__ = "헬스장 회원의 출석률에 기반한 개인화된 알림 메시지 시스템"

# 주요 모듈 가져오기
from notification.langchain import (
    process_user_notification,
    process_all_users,
    get_user_data,
    get_attendance_rate
)

# 패키지 초기화 로직
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

__all__ = [
    'process_user_notification',
    'process_all_users',
    'get_user_data',
    'get_attendance_rate'
] 