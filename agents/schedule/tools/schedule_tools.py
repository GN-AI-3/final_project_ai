from datetime import datetime, timedelta
from langchain.agents import tool
from database import db
from utils.date_utils import validate_date_format
from utils.general_utils import generate_reservation_no, format_schedule_result

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@tool
def get_user_schedule(input: str) -> str:
    """사용자의 예약 일정을 조회합니다."""
    try:
        # pt_linked_id 추출 (예제: input에서 id를 받아오는 방식으로 변경 가능)
        pt_linked_id = 5
        
        # 쿼리 실행
        query = f"""
        SELECT start_time,
        reservation_no
        FROM reservations
        WHERE pt_linked_id = {pt_linked_id}
        AND start_time > CURRENT_TIMESTAMP
        AND state = 'confirmed'
        ORDER BY start_time
        """
        
        results = db.run(query)
        
        # 결과를 general_utils의 format_schedule_result 함수로 전달
        return format_schedule_result(str(results))
        
    except Exception as e:
        return f"일정 조회 중 오류가 발생했습니다: {str(e)}"


def _check_same_day(start_dt: datetime) -> str:
    """당일 예약 여부를 확인합니다."""
    now = datetime.now()
    if (start_dt.year == now.year and 
        start_dt.month == now.month and 
        start_dt.day == now.day):
        return "죄송해요. 당일 예약은 불가능해요. 오늘 이후의 날짜를 선택해주세요."
    return None

def _check_future_date(start_dt: datetime) -> str:
    """미래 날짜 여부를 확인합니다."""
    now = datetime.now()
    if start_dt <= now:
        return "죄송해요. 과거 시간으로는 예약할 수 없어요. 오늘 이후의 날짜를 선택해주세요."
    return None

def _check_date_diff(start_dt: datetime, user_response: str = None) -> str:
    """예약 날짜와 현재 날짜의 차이를 확인합니다."""
    now = datetime.now()
    date_diff = (start_dt.date() - now.date()).days
    
    if date_diff >= 28:
        if user_response and user_response.lower() in ['예', '네', 'yes', 'y']:
            return None
        return f"예약하려는 날짜가 {date_diff}일 후예요. 먼 미래의 예약은 변경이나 취소가 어려울 수 있어요. 그래도 계속 진행하시겠어요? (계속하려면 '예'라고 입력해주세요)"
    return None

def _check_existing_reservation(start_dt: datetime, end_dt: datetime) -> str:
    """해당 시간대에 이미 예약이 있는지 확인합니다."""
    
    check_query = f"""
    SELECT COUNT(*)
    FROM reservations
    WHERE pt_linked_id = 5
    AND (
        (start_time <= '{start_dt}' AND end_time > '{start_dt}')
        OR (start_time < '{end_dt}' AND end_time >= '{end_dt}')
        OR (start_time >= '{start_dt}' AND end_time <= '{end_dt}')
    );
    """
    
    result = db.run(check_query)
    
    if result and result != "데이터가 없어요.":
        try:
            count = eval(result)[0][0]
            if count > 0:
                return "죄송해요. 해당 시간대에 이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
        except Exception as e:
            return f"죄송해요. 예약 확인 중에 오류가 발생했어요: {str(e)}"
    return None

@tool
def add_reservation(day: str, hour: int, month: str = None, user_response: str = None) -> str:
    """예약을 추가합니다.
    
    Args:
        day: 예약할 날짜 (YYYY-MM-DD 형식 또는 '내일', '모레' 등)
        hour: 예약할 시간 (0-23)
        month: 예약할 월 (선택사항)
        user_response: 사용자의 응답 (선택사항)
        
    Returns:
        str: 예약 결과 메시지
    """
    try:
        # 현재 날짜 출력
        now = datetime.now()
        logger.info(f"시스템 현재 날짜와 시간: {now}")
        
        # 날짜와 시간 검증
        start_dt, end_dt = validate_date_format(day, str(hour), month)
        if start_dt is None:
            return end_dt  # 에러 메시지 반환
            
        logger.info(f"검증된 예약 시작 시간: {start_dt}")
        logger.info(f"검증된 예약 종료 시간: {end_dt}")
        
        # 1. 당일 예약 체크
        error = _check_same_day(start_dt)
        if error:
            return error
            
        # 2. 미래 날짜 체크
        error = _check_future_date(start_dt)
        if error:
            return error
            
        # 3. 날짜 차이 체크
        message = _check_date_diff(start_dt, user_response)
        if message:
            return message
            
        # 4. 중복 예약 체크
        error = _check_existing_reservation(start_dt, end_dt)
        if error:
            return error
            
        # 예약 번호 생성
        reservation_no = generate_reservation_no()
        
        # 예약 추가
        query = f"""
        INSERT INTO reservations (reservation_no, start_time, end_time, pt_linked_id, state)
        VALUES ('{reservation_no}', '{start_dt}', '{end_dt}', 5, 'confirmed')
        RETURNING reservation_id;
        """
        
        result = db.run(query)
        logger.info(f"예약 추가 쿼리 실행 결과: {result}")
        
        if result and "error" not in result.lower():
            # 예약이 성공적으로 추가되었는지 확인
            check_query = f"""
            SELECT reservation_id, start_time, end_time, state
            FROM reservations
            WHERE reservation_no = '{reservation_no}'
            AND pt_linked_id = 5;
            """
            check_result = db.run(check_query)
            logger.info(f"예약 확인 쿼리 실행 결과: {check_result}")
            
            if check_result and "error" not in check_result.lower():
                return f"예약이 성공적으로 추가되었습니다. 예약 번호: {reservation_no}, 시간: {start_dt.strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {end_dt.strftime('%H시 %M분')}"
            else:
                return f"예약이 추가되었지만 확인 중 오류가 발생했습니다: {check_result}"
        else:
            return f"예약 추가 중 오류가 발생했습니다: {result}"
            
    except Exception as e:
        return f"예약 처리 중 오류가 발생했어요: {str(e)}" 
