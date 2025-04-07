"""
운동 동기부여 에이전트 인스턴스 패키지
"""
from agents.exercise_motivation.agents.exercise_motivation_agent import ExerciseMotivationAgent

# 기본 에이전트 인스턴스 생성
default_agent = ExerciseMotivationAgent()

__all__ = ["default_agent", "ExerciseMotivationAgent"] 