from datetime import datetime
from langchain.agents import tool
from core.database import execute_query
from utils.date_utils import validate_date_format
from utils.general_utils import format_schedule_result, format_reservation_result
from utils.reservation_validator import check_same_day, check_future_date, check_existing_reservation
from typing import Optional

@tool
def get_user_schedule(input: str) -> str:
    """사용자의 예약 일정을 조회합니다."""
    try:
        pt_linked_id = 5
        
        query = f"""
        SELECT start_time, reservation_no
        FROM reservations
        WHERE pt_linked_id = {pt_linked_id}
        AND start_time > CURRENT_TIMESTAMP
        AND state = 'confirmed'
        ORDER BY start_time
        """
        
        results = execute_query(query)
        formatted_result = format_schedule_result(str(results))
        return formatted_result
        
    except Exception as e:
        return f"일정 조회 중 오류가 발생했습니다: {str(e)}"

@tool
def add_reservation(day: str, hour: int, month: str = None, user_response: str = None) -> str:
    """예약을 추가합니다."""
    try:
        # month가 None이 아닌 경우 문자열로 변환
        month_str = str(month) if month is not None else None
        start_dt, end_dt = validate_date_format(day, str(hour), month_str)
        
        if start_dt is None:
            return end_dt

        # 1. 당일 예약 방지
        error = check_same_day(start_dt)
        if error:
            return error

        # 2. 과거 날짜 예약 방지
        error = check_future_date(start_dt)
        if error:
            return error

        # 3. 예약 중복 방지
        error = check_existing_reservation(start_dt, end_dt)
        if error:
            return error

        # 4. 예약 추가
        query = f"""
        INSERT INTO reservations (start_time, end_time, pt_linked_id, state)
        VALUES ('{start_dt}', '{end_dt}', 5, 'confirmed')
        RETURNING reservation_no;
        """
        
        result = execute_query(query)
        return format_reservation_result(result, start_dt, end_dt)
            
    except Exception as e:
        return f"예약 처리 중 오류가 발생했어요: {str(e)}"

@tool
def modify_reservation(
    reservation_no: str, 
    action: str, 
    new_day: Optional[int] = None, 
    new_hour: Optional[int] = None, 
    new_month: Optional[int] = None,
    reason: Optional[str] = None
) -> str:
    """예약을 변경하거나 취소하는 함수
    
    Args:
        reservation_no (str): 예약 번호
        action (str): 수행할 동작 ('cancel' 또는 'change')
        new_day (Optional[int]): 변경할 날짜 (변경 시 필요)
        new_hour (Optional[int]): 변경할 시간 (변경 시 필요)
        new_month (Optional[int]): 변경할 월 (변경 시 필요)
        reason (Optional[str]): 취소/변경 사유
    """
    try:
        pt_linked_id = 5  # 하드코딩된 pt_linked_id
        
        # 예약 번호가 없는 경우, 현재 예약 목록을 조회
        if not reservation_no:
            query = f"""
            SELECT reservation_no, start_time, end_time
            FROM reservations
            WHERE pt_linked_id = {pt_linked_id}
            AND start_time > CURRENT_TIMESTAMP
            AND state = 'confirmed'
            ORDER BY start_time
            """
            results = execute_query(query)
            
            if not results or results == "데이터가 없습니다.":
                return "현재 예약된 일정이 없어요. 예약 번호를 다시 확인해주세요."
            
            return format_schedule_result(str(results))
        
        # 예약 번호로 해당 예약이 존재하는지 확인
        check_query = f"""
        SELECT start_time, end_time
        FROM reservations
        WHERE pt_linked_id = {pt_linked_id}
        AND reservation_no = '{reservation_no}'
        AND state = 'confirmed'
        """
        
        result = execute_query(check_query)
        
        if not result or result == "데이터가 없습니다.":
            return "해당 예약 번호를 찾을 수 없어요. 예약 번호를 다시 확인해주세요."
        
        # 취소인 경우
        if action == "cancel":
            # 사유가 없는 경우 기본 메시지 설정
            if not reason:
                reason = "개인 사정"
                
            update_query = f"""
            UPDATE reservations
            SET state = 'cancelled',
                reason = '{reason}',
                updated_at = CURRENT_TIMESTAMP
            WHERE pt_linked_id = {pt_linked_id}
            AND reservation_no = '{reservation_no}'
            AND state = 'confirmed'
            RETURNING start_time;
            """
            
            result = execute_query(update_query)
            
            if result and result != "데이터가 없습니다.":
                formatted_result = format_schedule_result(str([(result, reservation_no)]))
                return f"예약 번호 {reservation_no}에 해당하는 일정({formatted_result})을 취소해드렸어요. (사유: {reason})"
            return "예약 취소에 실패했어요. 다시 시도해주세요."
        
        # 변경인 경우 (modify 또는 change)
        elif action in ["change", "modify"]:
            if not new_day or new_hour is None:
                return "변경할 날짜와 시간을 모두 입력해주세요."
            
            # 새로운 날짜/시간 검증
            if new_month is not None:
                date_str = f"{new_month}월 {new_day}일"
            else:
                date_str = str(new_day)
            
            # 시간 문자열 생성 (24시간 형식)
            hour_str = str(new_hour)
            
            start_dt, end_dt = validate_date_format(date_str, hour_str)
            if start_dt is None:
                return end_dt
            
            # 당일 예약 방지
            error = check_same_day(start_dt)
            if error:
                return error
            
            # 과거 날짜 예약 방지
            error = check_future_date(start_dt)
            if error:
                return error
            
            # 중복 예약 확인
            error = check_existing_reservation(start_dt, end_dt)
            if error:
                return error
            
            # 사유가 없는 경우 기본 메시지 설정
            if not reason:
                reason = "개인 사정"
            
            # 예약 변경
            update_query = f"""
            UPDATE reservations
            SET state = 'changed',
                reason = '{reason}',
                updated_at = CURRENT_TIMESTAMP
            WHERE pt_linked_id = {pt_linked_id}
            AND reservation_no = '{reservation_no}'
            AND state = 'confirmed'
            RETURNING start_time;
            """
            
            result = execute_query(update_query)
            
            if result and result != "데이터가 없습니다.":
                # 새로운 예약 추가
                insert_query = f"""
                INSERT INTO reservations (start_time, end_time, pt_linked_id, state, reason)
                VALUES ('{start_dt}', '{end_dt}', {pt_linked_id}, 'confirmed', '{reason}')
                RETURNING reservation_no;
                """
                
                new_result = execute_query(insert_query)
                
                if new_result and new_result != "데이터가 없습니다.":
                    try:
                        new_reservation_no = eval(new_result)[0][0]
                        
                        # 기존 예약 정보 포맷팅
                        old_formatted = format_schedule_result(str([(result, reservation_no)]))
                        
                        # 새로운 예약 정보 포맷팅
                        new_formatted = format_schedule_result(str([(new_result, new_reservation_no)]))
                        
                        return f"{old_formatted} 예약을 {new_formatted}로 변경해드렸어요. (사유: {reason})"
                    except Exception as e:
                        return "예약이 변경되었지만, 새로운 예약 번호를 확인할 수 없어요."
            return "예약 변경에 실패했어요. 다시 시도해주세요."
        
        return "잘못된 작업입니다. 'cancel' 또는 'change'를 지정해주세요."
            
    except Exception as e:
        return f"예약 처리 중 오류가 발생했어요: {str(e)}" 
