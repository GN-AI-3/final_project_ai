from datetime import datetime
from core.database import execute_query

def check_same_day(start_dt: datetime) -> str:
    """당일 예약 여부를 확인합니다."""
    now = datetime.now()
    
    if (start_dt.year == now.year and 
        start_dt.month == now.month and 
        start_dt.day == now.day):
        return "죄송해요. 당일 예약은 불가능해요. 오늘 이후의 날짜를 선택해주세요."
    return None

def check_future_date(start_dt: datetime) -> str:
    """미래 날짜 여부를 확인합니다."""
    now = datetime.now()
    
    if start_dt <= now:
        return "죄송해요. 과거 시간으로는 예약할 수 없어요. 오늘 이후의 날짜를 선택해주세요."
    return None

def check_existing_reservation(start_dt: datetime, end_dt: datetime) -> str:
    """해당 시간대에 이미 예약이 있는지 확인합니다."""
    start_time_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    check_query = f"""
    SELECT start_time, end_time
    FROM reservations
    WHERE pt_linked_id = 5
    AND state = 'confirmed'
    AND (
        (start_time <= '{start_time_str}' AND end_time > '{start_time_str}')
        OR (start_time < '{end_time_str}' AND end_time >= '{end_time_str}')
        OR (start_time >= '{start_time_str}' AND end_time <= '{end_time_str}')
    )
    LIMIT 1;
    """
    
    result = execute_query(check_query)
    
    # 결과가 없거나 "데이터가 없습니다"인 경우
    if not result or result == "데이터가 없습니다.":
        return None
    
    try:
        # 결과가 리스트 형태인 경우
        if isinstance(result, list):
            if result:
                existing_start = result[0][0]
                existing_end = result[0][1]
                return f"죄송해요. 해당 시간대({existing_start} ~ {existing_end})에 이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
        
        # 결과가 문자열인 경우 파싱 시도
        parsed_result = eval(result)
        if parsed_result:
            existing_start = parsed_result[0][0]
            existing_end = parsed_result[0][1]
            return f"죄송해요. 해당 시간대({existing_start} ~ {existing_end})에 이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
    except Exception as e:
        return f"죄송해요. 예약 확인 중에 오류가 발생했어요: {str(e)}"
    
    return None 