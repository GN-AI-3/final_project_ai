import os
from langchain_teddynote import logging
from graph import run_graph_simulation

# LangSmith 로그 설정
PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "default_project")
if PROJECT_NAME:
    logging.langsmith(PROJECT_NAME)

# 실행
if __name__ == "__main__":
    run_graph_simulation() 