import os

from langchain_teddynote import logging

# LangSmith 로그 설정
PROJECT_NAME = os.getenv("LANGSMITH_PROJECT")
if PROJECT_NAME:
    logging.langsmith(PROJECT_NAME)


def main():
    """메인 함수"""
    pass


if __name__ == "__main__":
    main()