"""
로깅 설정을 위한 유틸리티 모듈
"""
import logging
import os
import sys
from datetime import datetime

def setup_logger(name=None, level=logging.INFO, log_file=None):
    """
    애플리케이션에서 사용할 로거를 설정합니다.
    
    Args:
        name (str, optional): 로거 이름. 기본값은 루트 로거
        level (int, optional): 로깅 레벨. 기본값은 INFO
        log_file (str, optional): 로그 파일 경로. 기본값은 None (파일 로깅 비활성화)
        
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    # 로거 생성 (이름이 없으면 루트 로거 사용)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거
    if logger.handlers:
        logger.handlers.clear()
    
    # 콘솔 출력용 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 포맷 설정
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 로깅 설정 (선택 사항)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger 