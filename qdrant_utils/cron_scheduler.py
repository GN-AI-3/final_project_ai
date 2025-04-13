#!/usr/bin/env python3
"""
크론 스케줄러 - 데이터 분석기를 크론 작업으로 실행

이 스크립트는 crontab에 등록하여 매일 00시에 실행되도록 설정할 수 있습니다.
다음과 같이 crontab에 추가하세요:
0 0 * * * /path/to/python /path/to/qdrant_utils/cron_scheduler.py

또는 systemd 타이머로 설정할 수 있습니다.
"""

import os
import sys
import logging
import subprocess
from datetime import datetime, timedelta

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("qdrant_utils/logs/cron_scheduler.log", mode='a')
    ]
)
logger = logging.getLogger(__name__)

def run_data_analyzer():
    """데이터 분석기 실행"""
    try:
        # 스크립트 경로 (현재 파일과 같은 디렉토리에 있다고 가정)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_analyzer_path = os.path.join(script_dir, 'data_analyzer.py')
        
        # 어제 날짜 계산
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 데이터 분석기 실행 (어제 날짜 데이터 분석)
        logger.info(f"데이터 분석기 실행 - 날짜: {yesterday}")
        
        # 로그 디렉토리 확인
        os.makedirs("qdrant_utils/logs", exist_ok=True)
        
        # 파이썬 모듈로 실행 (-m 옵션 사용)
        result = subprocess.run(
            [sys.executable, "-m", "qdrant_utils.data_analyzer", "--mode", "run"],
            capture_output=True,
            text=True
        )
        
        # 결과 로깅
        if result.returncode == 0:
            logger.info("데이터 분석 성공!")
            if result.stdout:
                logger.info(f"출력: {result.stdout}")
        else:
            logger.error(f"데이터 분석 실패 (코드: {result.returncode})")
            if result.stderr:
                logger.error(f"오류: {result.stderr}")
            if result.stdout:
                logger.info(f"출력: {result.stdout}")
        
        return result.returncode == 0
    
    except Exception as e:
        logger.error(f"데이터 분석기 실행 중 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("크론 스케줄러 시작")
    success = run_data_analyzer()
    logger.info(f"크론 스케줄러 종료 - 성공: {success}")
    sys.exit(0 if success else 1) 