"""
Exercise Motivation Agent 테스트 스크립트

이 스크립트는 ExerciseMotivationAgent의 주요 기능을 테스트하고 응답값만 표시합니다.
"""
import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock

# 로깅 끄기 (로그 메시지 숨기기)
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger().setLevel(logging.CRITICAL)

# 경고 메시지 무시
import warnings
warnings.filterwarnings("ignore")

# OpenAI API 키 설정 (환경 변수에서 가져오기, 없으면 기본값 사용)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# LangChain의 디버그 로그 제거
os.environ["LANGCHAIN_HANDLER"] = "langchain"
os.environ["LANGCHAIN_VERBOSE"] = "false"

# 테스트 대상 클래스 임포트
from agents import ExerciseMotivationAgent

# 모의 DB 도구와 스케줄 도구 임포트
from agents.exercise_motivation.tools.mock_db import MockDBTools

# 가짜 운동 기록 생성 함수
def create_mock_records():
    """모의 운동 기록 데이터를 생성합니다"""
    from datetime import datetime, timedelta
    
    records = []
    today = datetime.now()
    
    # 지난 4주 동안의 운동 기록 생성
    for i in range(30):
        if i % 2 == 0:  # 격일로 운동
            date = today - timedelta(days=i)
            
            record = {
                "id": i + 1,
                "user_id": 1,
                "exercise_date": date.strftime('%Y-%m-%d'),
                "created_at": date.strftime('%Y-%m-%d %H:%M:%S'),
                "exercise_time": 60,  # 60분 운동
                "exercise_type": "러닝" if i % 4 == 0 else "웨이트",
                "memo": "오늘 운동 잘했다!" if i % 3 == 0 else ""
            }
            records.append(record)
    
    return records

class TestExerciseMotivationAgent(unittest.TestCase):
    """ExerciseMotivationAgent 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 실제 LLM 호출을 막고 미리 정의된 응답 반환
        self.llm_patcher = patch('langchain_openai.ChatOpenAI')
        self.mock_llm = self.llm_patcher.start()
        
        # 가짜 LLM 응답 설정
        mock_response = MagicMock()
        mock_response.content = "당신은 운동을 꾸준히 하고 있네요! 앞으로도 화이팅하세요! 💪"
        self.mock_llm.return_value.invoke.return_value = mock_response
        
        # DB 도구 패치 - 가짜 운동 기록 사용
        self.mock_records = create_mock_records()
        self.db_patcher = patch('agents.exercise_motivation.tools.db_tools.ExerciseDBTools')
        self.mock_db = self.db_patcher.start()
        self.mock_db.get_user_exercise_records.return_value = self.mock_records
        self.mock_db.get_exercise_pattern.return_value = {
            "pattern": "active", 
            "total_records": 15, 
            "attendance_rate": 0.75, 
            "memo_rate": 0.5
        }
        self.mock_db.get_exercise_weeks.return_value = 2
        self.mock_db.analyze_exercise_time.return_value = {
            "preferred_time": "09:00", 
            "morning_ratio": 0.6, 
            "afternoon_ratio": 0.3, 
            "evening_ratio": 0.1, 
            "most_active_day": "월요일", 
            "time_consistency": "high"
        }
        self.mock_db.save_motivation_message.return_value = True
        
        # 스케줄 도구 패치
        self.schedule_patcher = patch('agents.exercise_motivation.tools.schedule_tools.ScheduleTools')
        self.mock_schedule = self.schedule_patcher.start()
        self.mock_schedule.schedule_motivation_message.return_value = True
        self.mock_schedule.set_mobile_alarm.return_value = True
        
        # 패턴 상세 설명 함수 패치
        self.pattern_details_patcher = patch('agents.exercise_motivation.prompts.motivation_prompts.get_pattern_details')
        self.mock_pattern_details = self.pattern_details_patcher.start()
        self.mock_pattern_details.return_value = "꾸준히 운동을 진행하고 있는 패턴입니다."
        
        # 템플릿 선택 함수 패치
        self.template_patcher = patch('agents.exercise_motivation.prompts.motivation_prompts.get_motivation_prompt_template')
        self.mock_template = self.template_patcher.start()
        mock_template = MagicMock()
        mock_template.format_messages.return_value = [
            {"role": "system", "content": "당신은 동기부여 에이전트입니다"}, 
            {"role": "user", "content": "운동 동기부여 메시지를 생성해주세요"}
        ]
        self.mock_template.return_value = mock_template
        
        # 에이전트 인스턴스 생성
        self.agent = ExerciseMotivationAgent()
    
    def tearDown(self):
        """테스트 정리"""
        self.llm_patcher.stop()
        self.db_patcher.stop()
        self.schedule_patcher.stop()
        self.pattern_details_patcher.stop()
        self.template_patcher.stop()
    
    def test_generate_motivation_message(self):
        """동기부여 메시지 생성 테스트"""
        print("\n=== 동기부여 메시지 생성 테스트 ===")
        
        # 테스트 실행
        message = self.agent.generate_motivation_message(user_id=1)
        
        # 응답 결과만 출력
        print(f"응답 메시지: {message}")
    
    def test_process_message(self):
        """메시지 처리 테스트"""
        print("\n=== 메시지 처리 테스트 ===")
        
        # 일반 메시지
        response = self.agent._process_message("오늘 운동이 힘들어요", user_id=1)
        print(f"일반 메시지 응답: {response}")
        
        # 스케줄 메시지
        response = self.agent._process_message("운동 메시지 예약해주세요", user_id=1)
        print(f"스케줄 메시지 응답: {response}")
    
    def test_schedule_motivation_message(self):
        """동기부여 메시지 스케줄링 테스트"""
        print("\n=== 동기부여 메시지 스케줄링 테스트 ===")
        
        # 1-2주차 테스트
        self.mock_db.get_exercise_weeks.return_value = 2
        success = self.agent.schedule_motivation_message(user_id=1)
        print(f"1-2주차 사용자 스케줄링 결과: {success}")
        
        # 3주차 이상 테스트
        self.mock_db.get_exercise_weeks.return_value = 4
        success = self.agent.schedule_motivation_message(user_id=1)
        print(f"3주차 이상 사용자 스케줄링 결과: {success}")


if __name__ == "__main__":
    # 타이틀 출력
    print("\n========================================================")
    print("     Exercise Motivation Agent 테스트 결과 (응답값 전용)     ")
    print("========================================================\n")
    
    # 테스트 실행 (결과만 표시하기 위해 일반 unittest 실행 대신 직접 실행)
    test = TestExerciseMotivationAgent()
    
    try:
        test.setUp()
        test.test_generate_motivation_message()
        test.test_process_message()
        test.test_schedule_motivation_message()
    finally:
        test.tearDown()
    
    print("\n========================================================")
    print("               모든 테스트가 완료되었습니다                 ")
    print("========================================================\n") 