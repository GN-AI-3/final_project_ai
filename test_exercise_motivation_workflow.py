"""
Exercise Motivation Workflow 테스트 스크립트

이 스크립트는 운동 동기부여 워크플로우를 테스트합니다.
"""
import os
import logging
import unittest.mock as mock
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 모의 데이터베이스 및 모듈 패치
from agents.exercise_motivation.tools.mock_db import MockDBTools
from agents.exercise_motivation.tools.schedule_tools import ScheduleTools

# 실제 DB 도구 대신 모의 DB 도구로 패치
import agents.exercise_motivation.workflows.exercise_motivation_workflow as workflow_module
import agents.exercise_motivation.tools.db_tools as db_module

# 패치 적용
workflow_module.ExerciseDBTools = MockDBTools
db_module.ExerciseDBTools = MockDBTools

# 스케줄링 도구 모의 패치
def mock_schedule_motivation_message(*args, **kwargs):
    logger.info("모의 동기부여 메시지 스케줄링 호출됨")
    return True

def mock_set_mobile_alarm(*args, **kwargs):
    logger.info("모의 모바일 알람 설정 호출됨")
    return True

ScheduleTools.schedule_motivation_message = mock_schedule_motivation_message
ScheduleTools.set_mobile_alarm = mock_set_mobile_alarm

# 워크플로우 임포트
from agents.exercise_motivation.workflows.exercise_motivation_workflow import (
    create_exercise_motivation_workflow
)

def test_exercise_workflow():
    """운동 동기부여 워크플로우 테스트"""
    
    logger.info("=== 운동 동기부여 워크플로우 테스트 시작 ===")
    
    # 워크플로우 생성
    workflow = create_exercise_motivation_workflow()
    
    # 테스트 케이스
    test_cases = [
        {
            "user_id": 1,
            "description": "적극적인 사용자 (Active User)"
        },
        {
            "user_id": 2,
            "description": "불규칙적 사용자 (Irregular User)"
        },
        {
            "user_id": 3,
            "description": "비활성 사용자 (Inactive User)"
        },
        {
            "user_id": 4,
            "description": "신규 사용자 (New User)"
        }
    ]
    
    # 각 테스트 케이스 실행
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n=== 테스트 케이스 {i}: {test_case['description']} ===")
        logger.info(f"사용자 ID: {test_case['user_id']}")
        
        # 워크플로우 실행
        try:
            response = workflow(test_case["user_id"])
            logger.info(f"워크플로우 응답: {response}")
        except Exception as e:
            logger.error(f"워크플로우 실행 중 오류: {str(e)}")
    
    logger.info("\n=== 운동 동기부여 워크플로우 테스트 완료 ===")

if __name__ == "__main__":
    logger.info("Exercise Motivation Workflow 테스트 시작")
    
    # 워크플로우 테스트
    test_exercise_workflow()
    
    logger.info("Exercise Motivation Workflow 테스트 완료") 