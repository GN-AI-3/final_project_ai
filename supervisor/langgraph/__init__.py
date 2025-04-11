"""
LangGraph 모듈 초기화
LangGraph 기반 파이프라인 구성 요소 및 설정
"""

import logging
import os
import sys

# 로깅 설정
def setup_logging():
    """LangGraph 로깅 설정"""
    logger = logging.getLogger('supervisor.langgraph')
    logger.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # 파일 핸들러 추가
    file_handler = logging.FileHandler('langgraph_debug.log')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # 핸들러 등록
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # 자식 로거에도 적용
    for name in ['nodes', 'state']:
        child_logger = logging.getLogger(f'supervisor.langgraph.{name}')
        child_logger.setLevel(logging.DEBUG)
        child_logger.propagate = True
    
    return logger

# 로깅 초기화
logger = setup_logging()
logger.info("LangGraph 모듈 초기화 완료") 