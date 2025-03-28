#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
헬스장 자동 결석 처리 스크립트
이 스크립트는 매일 실행되어 전날 출석하지 않은 회원을 자동으로 결석 처리합니다.
cron job으로 등록하여 매일 자정 이후 실행하는 것이 좋습니다.
"""
import os
import logging
from dotenv import load_dotenv
from datetime import date
from db_models import AttendanceModel, MemberModel

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_absence.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """자동 결석 처리 메인 함수"""
    # 환경 변수 로드
    load_dotenv()
    
    logger.info("자동 결석 처리 시작...")
    
    # 자동 결석 처리 함수 실행
    try:
        absence_count = AttendanceModel.process_auto_absences()
        
        # 어제 날짜 계산
        yesterday = date.today().strftime('%Y-%m-%d')
        logger.info(f"{yesterday} 날짜에 총 {absence_count}명의 회원이 결석 처리되었습니다.")
        
        # 결석한 회원 목록 조회
        query = f"""
        SELECT m.id, m.name, m.email, m.goal
        FROM attendance a
        JOIN member m ON a.member_id = m.id
        WHERE a.attendance_date = '{yesterday}' AND a.status = '결석'
        ORDER BY m.id
        """
        
        from pgdatabase import connect_to_database
        conn = connect_to_database()
        if conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            
            logger.info(f"결석 회원 목록 ({len(results)}명):")
            for result in results:
                member_id, name, email, goal = result
                logger.info(f"회원 ID: {member_id}, 이름: {name}, 이메일: {email}, 목표: {goal}")
            
            cursor.close()
            conn.close()
        
    except Exception as e:
        logger.error(f"자동 결석 처리 중 오류 발생: {str(e)}", exc_info=True)
    
    logger.info("자동 결석 처리 완료")

if __name__ == "__main__":
    main() 