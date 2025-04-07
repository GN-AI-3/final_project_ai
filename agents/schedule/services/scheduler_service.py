import schedule
import time
from threading import Thread
from core.database import execute_query

def update_expired_reservations():
    """만료된 예약을 업데이트합니다."""
    query = """
    UPDATE reservations
    SET state = 'expired'
    WHERE end_time < CURRENT_TIMESTAMP
    AND state = 'confirmed'
    """
    execute_query(query)

def run_scheduler():
    """스케줄러를 실행합니다."""
    schedule.every(1).minutes.do(update_expired_reservations)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    """스케줄러를 별도 스레드에서 시작합니다."""
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start() 