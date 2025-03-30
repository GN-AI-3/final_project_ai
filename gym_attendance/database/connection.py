"""
데이터베이스 연결 관리 모듈
"""
import os
import logging
import psycopg2
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_db_connection():
    """
    PostgreSQL 데이터베이스 연결을 생성합니다.
    
    Returns:
        psycopg2.extensions.connection: 데이터베이스 연결 객체
    """
    try:
        # 환경 변수 로드
        load_dotenv()
        
        # 데이터베이스 연결 정보
        db_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'dbname': os.getenv('DB_NAME', 'gym'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '1234')
        }
        
        # 데이터베이스 연결
        conn = psycopg2.connect(**db_params)
        logger.info("데이터베이스 연결 성공")
        
        return conn
        
    except Exception as e:
        logger.error(f"데이터베이스 연결 중 오류 발생: {str(e)}")
        raise 