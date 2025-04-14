from datetime import datetime
from ..core.database import execute_query

def check_same_day(start_dt: datetime) -> str:
    """당일 예약 여부를 확인합니다."""
    try:
        now = datetime.now()
        
        if (start_dt.year == now.year and 
            start_dt.month == now.month and 
            start_dt.day == now.day):
            return "죄송해요. 당일 예약은 불가능해요. 오늘 이후의 날짜를 선택해주세요."
        return None
    except Exception as e:
        return f"당일 예약 확인 중 오류가 발생했습니다: {str(e)}"

def check_future_date(start_dt: datetime) -> str:
    """미래 날짜 여부를 확인합니다."""
    try:
        now = datetime.now()
        
        if start_dt <= now:
            return "죄송해요. 과거 시간으로는 예약할 수 없어요. 오늘 이후의 날짜를 선택해주세요."
        return None
    except Exception as e:
        return f"미래 날짜 확인 중 오류가 발생했습니다: {str(e)}"

def check_existing_schedule(start_dt: datetime, end_dt: datetime) -> str:
    """해당 시간대에 이미 예약이 있는지 확인합니다."""
    try:
        start_time_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        check_query = f"""
        SELECT start_time, end_time
        FROM pt_schedule
        WHERE pt_contract_id = 7
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
        
        # 결과가 리스트 형태인 경우
        if isinstance(result, list) and result:
            existing_start = result[0][0]
            existing_end = result[0][1]
            
            # datetime 객체인지 확인
            if isinstance(existing_start, datetime) and isinstance(existing_end, datetime):
                start_str = existing_start.strftime('%Y-%m-%d %H:%M')
                end_str = existing_end.strftime('%H:%M')
                return f"죄송해요. 해당 시간대({start_str} ~ {end_str})에 이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
            else:
                return f"죄송해요. 해당 시간대에 이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
        
        return None
        
    except Exception as e:
        return f"예약 중복 확인 중 오류가 발생했습니다: {str(e)}" 