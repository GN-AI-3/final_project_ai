from datetime import datetime
from typing import Optional, Tuple, List, Union

from langchain.agents import tool

from core.database import execute_query
from utils.date_utils import validate_date_format
from utils.general_utils import format_schedule_result, format_reservation_result
from utils.reservation_validator import (
    check_same_day,
    check_future_date,
    check_existing_reservation
)


@tool
def get_user_schedule(input: str = "") -> str:
    """사용자의 예약 일정을 조회합니다.
    
    Args:
        input: 사용자 입력 (사용되지 않음)
        
    Returns:
        str: 예약 일정 목록 또는 에러 메시지
    """
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
        
        # 결과가 문자열인 경우 그대로 반환
        if isinstance(results, str):
            return results
            
        # 결과가 리스트인 경우 포맷팅
        formatted_result = format_schedule_result(str(results))
        return formatted_result
        
    except Exception as e:
        return f"일정 조회 중 오류가 발생했습니다: {str(e)}"


@tool
def add_reservation(day: str, hour: str, month: Optional[str] = None) -> str:
    """예약을 추가합니다.
    
    Args:
        day: 예약할 날짜 (문자열로 입력)
        hour: 예약할 시간 (문자열로 입력)
        month: 예약할 월 (선택적, 문자열로 입력)
        
    Returns:
        str: 예약 결과 또는 에러 메시지
    """
    try:
        # month가 None이 아닌 경우 문자열로 변환
        month_str = str(month) if month is not None else None
        
        start_dt, end_dt = validate_date_format(day, hour, month_str)
        
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
    """예약을 취소하거나 변경합니다.
    
    Args:
        reservation_no: 예약 번호
        action: 수행할 작업 ('cancel' 또는 'change')
        new_day: 새로운 예약 일자 (action이 'change'일 때만 필요)
        new_hour: 새로운 예약 시간 (action이 'change'일 때만 필요)
        new_month: 새로운 예약 월 (선택적)
        reason: 취소 또는 변경 사유
        
    Returns:
        str: 작업 결과 메시지
    """
    try:
        # pt_linked_id 설정 (실제로는 사용자 인증에서 가져와야 함)
        pt_linked_id = 5  # 테스트용 고정값
        
        # 예약 번호 확인
        check_query = f"""
        SELECT start_time, end_time, state
        FROM reservations
        WHERE pt_linked_id = {pt_linked_id}
        AND reservation_no = '{reservation_no}'
        """
        
        result = execute_query(check_query)
        
        if not result or result == "데이터가 없습니다.":
            return f"예약 번호 {reservation_no}에 해당하는 예약을 찾을 수 없습니다."
        
        # 예약 상태 확인
        reservation_state = None
        if result and result != "데이터가 없습니다.":
            try:
                # 결과가 튜플 리스트인 경우 처리
                if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple) and len(result[0]) > 2:
                    reservation_state = result[0][2]
                # 결과가 문자열인 경우 처리
                elif isinstance(result, str):
                    # 문자열에서 상태 정보 추출 시도
                    if "state" in result.lower():
                        import re
                        state_match = re.search(r"state\s*=\s*['\"]([^'\"]+)['\"]", result, re.IGNORECASE)
                        if state_match:
                            reservation_state = state_match.group(1)
            except Exception:
                pass
        
        # 이미 취소된 예약인 경우
        if reservation_state == 'cancelled':
            return f"예약 번호 {reservation_no}는 이미 취소되었습니다."
        
        # 사유가 없는 경우 사유를 요청
        if reason is None or reason.strip() == "":
            if action == "cancel":
                return "예약을 취소하려면 취소 사유를 알려주세요."
            else:
                return "예약을 변경하려면 변경 사유를 알려주세요."
        
        # 예약 취소 처리
        if action == "cancel":
            cancel_query = f"""
            UPDATE reservations
            SET state = 'cancelled',
                reason = '{reason}',
                updated_at = CURRENT_TIMESTAMP
            WHERE pt_linked_id = {pt_linked_id}
            AND reservation_no = '{reservation_no}'
            AND state = 'confirmed'
            RETURNING start_time;
            """
            
            cancel_result = execute_query(cancel_query)
            
            if cancel_result and cancel_result != "데이터가 없습니다.":
                try:
                    # 결과가 튜플 리스트인 경우 처리
                    if isinstance(cancel_result, list) and len(cancel_result) > 0 and isinstance(cancel_result[0], tuple) and len(cancel_result[0]) > 0:
                        start_time = cancel_result[0][0]
                    else:
                        start_time = cancel_result
                        
                    if isinstance(start_time, datetime):
                        formatted_date = start_time.strftime("%Y년 %m월 %d일 %H시")
                    else:
                        formatted_date = str(start_time)
                    return f"{formatted_date} 예약이 취소되었습니다. 취소 사유: {reason}"
                except Exception:
                    return f"예약이 취소되었습니다. 취소 사유: {reason}"
            else:
                return "예약 취소에 실패했습니다."
        
        # 예약 변경 처리
        elif action == "change":
            # 날짜 검증
            start_dt, end_dt = validate_date_format(new_day, new_hour, new_month)
            
            if not start_dt or not end_dt:
                return "유효하지 않은 날짜 또는 시간입니다."
            
            # 당일 예약 체크
            error = check_same_day(start_dt)
            if error:
                return error
            
            # 과거 날짜 체크
            error = check_future_date(start_dt)
            if error:
                return error
            
            # 중복 예약 체크
            error = check_existing_reservation(start_dt, end_dt)
            if error:
                return error
            
            # 예약 상태 변경
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
            
            update_result = execute_query(update_query)
            
            if update_result and update_result != "데이터가 없습니다.":
                # 새 예약 추가
                insert_query = f"""
                INSERT INTO reservations (start_time, end_time, pt_linked_id, state)
                VALUES ('{start_dt}', '{end_dt}', {pt_linked_id}, 'confirmed')
                RETURNING reservation_no;
                """
                
                new_result = execute_query(insert_query)
                
                if new_result and new_result != "데이터가 없습니다.":
                    try:
                        # 결과가 튜플 리스트인 경우 처리
                        if isinstance(new_result, list) and len(new_result) > 0 and isinstance(new_result[0], tuple) and len(new_result[0]) > 0:
                            new_reservation_no = new_result[0][0]
                        else:
                            new_reservation_no = new_result
                            
                        # 결과 포맷팅
                        if isinstance(update_result, list) and len(update_result) > 0 and isinstance(update_result[0], tuple) and len(update_result[0]) > 0:
                            old_date = update_result[0][0]
                        else:
                            old_date = update_result
                            
                        if isinstance(old_date, datetime):
                            old_date_str = old_date.strftime("%Y년 %m월 %d일 %H시")
                        else:
                            old_date_str = str(old_date)
                            
                        new_date_str = start_dt.strftime("%Y년 %m월 %d일 %H시")
                        
                        return f"예약이 변경되었습니다.\n\n기존 예약: {old_date_str}\n새 예약: {new_date_str}\n변경 사유: {reason}"
                    except Exception as e:
                        return f"예약이 변경되었습니다. 변경 사유: {reason}"
                else:
                    return "새 예약 추가에 실패했습니다."
            else:
                return "예약 상태 변경에 실패했습니다."
        
        return "잘못된 작업입니다. 'cancel' 또는 'change'를 입력해주세요."
            
    except Exception as e:
        return f"예약 처리 중 오류가 발생했어요: {str(e)}" 
