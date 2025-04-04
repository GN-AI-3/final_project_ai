"""
Exercise Motivation Agent 테스트 스크립트

이 스크립트는 개인화된 운동 동기부여 에이전트를 테스트합니다.
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
import agents.exercise_motivation.models.exercise_motivation_agent as agent_module
import agents.exercise_motivation.tools.db_tools as db_module

# 패치 적용
agent_module.ExerciseDBTools = MockDBTools
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

# 에이전트 임포트
from agents.exercise_motivation.models.exercise_motivation_agent import ExerciseMotivationAgent

def test_user_messages():
    """사용자 메시지 테스트"""
    
    logger.info("=== 사용자 메시지 테스트 시작 ===")
    
    # 에이전트 초기화
    agent = ExerciseMotivationAgent()
    
    # 테스트 케이스
    test_cases = [
        {
            "user_id": 1,
            "message": "오늘 운동을 마쳤어요. 몸이 더 가벼워지는 느낌이에요.",
            "description": "적극적인 사용자 (Active User)"
        },
        {
            "user_id": 2,
            "message": "일이 너무 바빠서 운동을 못했어요. 내일은 꼭 해볼게요.",
            "description": "불규칙적 사용자 (Irregular User)"
        },
        {
            "user_id": 3,
            "message": "어떻게 운동을 시작해야 할지 모르겠어요.",
            "description": "비활성 사용자 (Inactive User)"
        }
    ]
    
    # 각 테스트 케이스 실행
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n=== 테스트 케이스 {i}: {test_case['description']} ===")
        logger.info(f"사용자 메시지: {test_case['message']}")
        
        # 에이전트 호출
        response = agent._process_message(
            test_case["message"], 
            user_id=test_case["user_id"]
        )
        
        logger.info(f"에이전트 응답: {response}")
    
    logger.info("\n=== 사용자 메시지 테스트 완료 ===")

def test_scheduled_messages():
    """스케줄링된 동기부여 메시지 테스트"""
    
    logger.info("\n=== 스케줄링 메시지 테스트 시작 ===")
    
    # 에이전트 초기화
    agent = ExerciseMotivationAgent()
    
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
        }
    ]
    
    # 각 테스트 케이스 실행
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n=== 테스트 케이스 {i}: {test_case['description']} ===")
        
        # 스케줄링 테스트 (실제로는 예약만 하고 전송하지 않음)
        success = agent.schedule_motivation_message(test_case["user_id"])
        
        if success:
            logger.info(f"사용자 {test_case['user_id']}에 대한 동기부여 메시지 스케줄링 성공")
        else:
            logger.error(f"사용자 {test_case['user_id']}에 대한 동기부여 메시지 스케줄링 실패")
    
    logger.info("\n=== 스케줄링 메시지 테스트 완료 ===")

if __name__ == "__main__":
    logger.info("Exercise Motivation Agent 테스트 시작")
    
    # 사용자 메시지 테스트
    test_user_messages()
    
    # 스케줄링된 메시지 테스트
    test_scheduled_messages()
    
    logger.info("Exercise Motivation Agent 테스트 완료") 