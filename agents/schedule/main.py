import os

from langchain_teddynote import logging

from graph import run_graph_simulation
from services.scheduler_service import start_scheduler

# LangSmith 로그 설정
PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "default_project")
if PROJECT_NAME:
    logging.langsmith(PROJECT_NAME)


def main():
    """메인 함수 - 스케줄러 및 그래프 시뮬레이션 실행"""
    # 스케줄러 시작
    start_scheduler()
    
    # 그래프 시뮬레이션 실행
    run_graph_simulation()


if __name__ == "__main__":
    main()