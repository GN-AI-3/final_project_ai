import schedule
import time
from threading import Thread
from core.database import execute_query

def update_expired_reservations() -> None:
    """만료된 예약을 업데이트합니다.
    
    만료된 예약의 상태를 'completed'로 변경합니다.
    """
    try:
        query = """
        UPDATE reservations
        SET state = 'completed'
        WHERE end_time < CURRENT_TIMESTAMP
        AND state = 'confirmed'
        """
        execute_query(query)
    except Exception as e:
        # 로깅 없이 조용히 실패
        pass

def run_scheduler() -> None:
    """스케줄러를 실행합니다.
    
    매 60분마다 만료된 예약을 업데이트합니다.
    """
    schedule.every(60).minutes.do(update_expired_reservations)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception:
            time.sleep(5)  # 오류 발생 시 5초 대기 후 재시도

def start_scheduler() -> None:
    """스케줄러를 별도 스레드에서 시작합니다.
    
    데몬 스레드로 실행되며, 메인 프로그램 종료 시 자동으로 종료됩니다.
    """
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start() 