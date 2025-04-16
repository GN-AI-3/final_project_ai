"""
로거 설정 모듈
애플리케이션 전반에 걸쳐 일관된 로깅 설정을 제공합니다.
"""

import logging
import os
from typing import Optional

# 로그 파일 경로
LOG_FILE = 'supervisor.log'

# 로그 레벨 설정
DEFAULT_LOG_LEVEL = logging.INFO

# 로거 캐시
_loggers = {}

def setup_logger(name: str, log_level: Optional[int] = None) -> logging.Logger:
    """
    로거를 설정합니다.
    
    Args:
        name: 로거 이름
        log_level: 로그 레벨 (기본값: INFO)
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    if log_level is None:
        log_level = DEFAULT_LOG_LEVEL
    
    # 이미 설정된 로거가 있으면 반환
    if name in _loggers:
        return _loggers[name]
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 핸들러가 이미 있는지 확인
    if logger.handlers:
        return logger
    
    # 포매터 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 파일 핸들러 추가
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # 로거 캐시에 저장
    _loggers[name] = logger
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    설정된 로거를 가져옵니다. 로거가 설정되지 않은 경우 새로 설정합니다.
    
    Args:
        name: 로거 이름
        
    Returns:
        logging.Logger: 로거 인스턴스
    """
    if name in _loggers:
        return _loggers[name]
    
    return setup_logger(name) 