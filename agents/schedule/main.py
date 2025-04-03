import os
import threading
import schedule
import time
from datetime import datetime
from langchain_teddynote import logging
from graph import run_graph_simulation
from database import db

# LangSmith 로그 설정
PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "default_project")
if PROJECT_NAME:
    logging.langsmith(PROJECT_NAME)

def update_expired_reservations():
    try:
        query = """
        UPDATE reservations
        SET state = 'completed'
        WHERE state = 'confirmed'
        AND end_time < CURRENT_TIMESTAMP;
        """
        
        db.run(query)
        print(f"{datetime.now()}: 예약 상태 업데이트 완료")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def run_scheduler():
    # 60분마다 실행
    schedule.every(60).minutes.do(update_expired_reservations)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # 스케줄러를 별도 스레드로 실행
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # 메인 스레드에서 챗봇 실행
    run_graph_simulation() 