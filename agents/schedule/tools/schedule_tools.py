from datetime import datetime
from typing import Optional
import json

from langchain.agents import tool

from core.database import execute_query
from utils.date_utils import validate_date_format
from utils.schedule_validator import (
    check_same_day,
    check_future_date,
    check_existing_schedule
)

pt_contract_id = 7

@tool
def get_user_schedule(input: str = "") -> str:
    """사용자의 스케줄을 조회합니다.
    
    Args:
        input: 사용자 입력 (사용되지 않음)
        
    Returns:
        str: 스케줄 목록 또는 에러 메시지
    """
    try:
        
        query = f"""
        SELECT start_time, reservation_id
        FROM pt_schedule
        WHERE pt_contract_id = {pt_contract_id}
        AND start_time > CURRENT_TIMESTAMP
        AND status = 'SCHEDULED'
        ORDER BY start_time
        """
        
        results = execute_query(query)
        
        # 결과가 문자열인 경우 에러 메시지 반환
        if isinstance(results, str):
            return json.dumps({
                "success": False,
                "error": results
            }, ensure_ascii=False)
            
        # 결과가 리스트인 경우 JSON 형식으로 변환
        if isinstance(results, list):
            schedules = []
            for result in results:
                if isinstance(result, tuple) and len(result) >= 2:
                    start_time, reservation_id = result
                    if isinstance(start_time, datetime):
                        formatted_time = start_time.strftime("%Y년 %m월 %d일 %H시")
                    else:
                        formatted_time = str(start_time)
                    
                    schedules.append({
                        "start_time": formatted_time,
                        "reservation_id": reservation_id
                    })
            
            response = {
                "success": True,
                "schedules": schedules
            }
            return json.dumps(response, ensure_ascii=False)
        
        return json.dumps({
            "success": False,
            "error": "예약 일정을 찾을 수 없습니다."
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"일정 조회 중 오류가 발생했습니다: {str(e)}"
        }, ensure_ascii=False)


@tool
def add_schedule(day: str, hour: str, month: Optional[str] = None) -> str:
    """스케줄을 추가합니다.
    
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
            return json.dumps({
                "success": False,
                "error": end_dt
            }, ensure_ascii=False)

        # 1. 당일 예약 방지
        error = check_same_day(start_dt)
        if error:
            return json.dumps({
                "success": False,
                "error": error
            }, ensure_ascii=False)

        # 2. 과거 날짜 예약 방지
        error = check_future_date(start_dt)
        if error:
            return json.dumps({
                "success": False,
                "error": error
            }, ensure_ascii=False)

        # 3. 예약 중복 방지
        error = check_existing_schedule(start_dt, end_dt)
        if error:
            return json.dumps({
                "success": False,
                "error": error
            }, ensure_ascii=False)

        # 4. 예약 추가
        query = f"""
        INSERT INTO pt_schedule (start_time, end_time, pt_contract_id, status)
        VALUES ('{start_dt}', '{end_dt}', {pt_contract_id}, 'SCHEDULED')
        RETURNING reservation_id;
        """
        
        result = execute_query(query)
        
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple) and len(result[0]) > 0:
            reservation_id = result[0][0]
            formatted_start = start_dt.strftime("%Y년 %m월 %d일 %H시")
            formatted_end = end_dt.strftime("%Y년 %m월 %d일 %H시")
            
            response = {
                "success": True,
                "reservation": {
                    "reservation_id": reservation_id,
                    "start_time": formatted_start,
                    "end_time": formatted_end
                }
            }
            return json.dumps(response, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": "예약 생성에 실패했습니다."
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"예약 처리 중 오류가 발생했어요: {str(e)}"
        }, ensure_ascii=False)


@tool
def modify_schedule(
    reservation_id: str,
    action: str,
    new_day: Optional[int] = None,
    new_hour: Optional[int] = None,
    new_month: Optional[int] = None,
    reason: Optional[str] = None
) -> str:
    """예약을 취소하거나 변경합니다.
    
    Args:
        reservation_id: 예약 번호
        action: 수행할 작업 ('cancel' 또는 'change')
        new_day: 새로운 예약 일자 (action이 'change'일 때만 필요)
        new_hour: 새로운 예약 시간 (action이 'change'일 때만 필요)
        new_month: 새로운 예약 월 (선택적)
        reason: 취소 또는 변경 사유
        
    Returns:
        str: 작업 결과 메시지
    """
    try:
        # 예약 번호 확인
        check_query = f"""
        SELECT start_time, end_time, status
        FROM pt_schedule
        WHERE pt_contract_id = {pt_contract_id}
        AND reservation_id = '{reservation_id}'
        """
        
        result = execute_query(check_query)
        
        if not result or result == "데이터가 없습니다.":
            return json.dumps({
                "success": False,
                "error": f"예약 번호 {reservation_id}에 해당하는 예약을 찾을 수 없습니다."
            }, ensure_ascii=False)
        
        # 예약 상태 확인
        reservation_status = None
        if result and result != "데이터가 없습니다.":
            try:
                # 결과가 튜플 리스트인 경우 처리
                if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple) and len(result[0]) > 2:
                    reservation_status = result[0][2]
                # 결과가 문자열인 경우 처리
                elif isinstance(result, str):
                    # 문자열에서 상태 정보 추출 시도
                    if "status" in result.lower():
                        import re
                        status_match = re.search(r"status\s*=\s*['\"]([^'\"]+)['\"]", result, re.IGNORECASE)
                        if status_match:
                            reservation_status = status_match.group(1)
            except Exception:
                pass
        
        # 이미 취소된 예약인 경우
        if reservation_status == 'CANCELLED':
            return json.dumps({
                "success": False,
                "error": f"예약 번호 {reservation_id}는 이미 취소되었습니다."
            }, ensure_ascii=False)
        
        # 사유가 없는 경우 사유를 요청
        if reason is None or reason.strip() == "":
            if action == "cancel":
                return json.dumps({
                    "success": False,
                    "error": "예약을 취소하려면 취소 사유를 알려주세요."
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": "예약을 변경하려면 변경 사유를 알려주세요."
                }, ensure_ascii=False)
        
        # 예약 취소 처리
        if action == "cancel":
            cancel_query = f"""
            UPDATE pt_schedule
            SET status = 'CANCELLED',
                reason = '{reason}'
            WHERE pt_contract_id = {pt_contract_id}
            AND reservation_id = '{reservation_id}'
            AND status = 'SCHEDULED'
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
                        
                    response = {
                        "success": True,
                        "action": "cancel",
                        "reservation": {
                            "reservation_id": reservation_id,
                            "start_time": formatted_date,
                            "reason": reason
                        }
                    }

                    return json.dumps(response, ensure_ascii=False)
                except Exception:
                    response = {
                        "success": True,
                        "action": "cancel",
                        "reservation": {
                            "reservation_id": reservation_id,
                            "reason": reason
                        }
                    }

                    return json.dumps(response, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": "예약 취소에 실패했습니다."
                }, ensure_ascii=False)
        
        # 예약 변경 처리
        elif action == "change":
            # 날짜 검증
            start_dt, end_dt = validate_date_format(new_day, new_hour, new_month)
            
            if not start_dt or not end_dt:
                return json.dumps({
                    "success": False,
                    "error": "유효하지 않은 날짜 또는 시간입니다."
                }, ensure_ascii=False)
            
            # 당일 예약 체크
            error = check_same_day(start_dt)
            if error:
                return json.dumps({
                    "success": False,
                    "error": error
                }, ensure_ascii=False)
            
            # 과거 날짜 체크
            error = check_future_date(start_dt)
            if error:
                return json.dumps({
                    "success": False,
                    "error": error
                }, ensure_ascii=False)
            
            # 중복 예약 체크
            error = check_existing_schedule(start_dt, end_dt)
            if error:
                return json.dumps({
                    "success": False,
                    "error": error
                }, ensure_ascii=False)
            
            # 예약 상태 변경
            update_query = f"""
            UPDATE pt_schedule
            SET status = 'CHANGED',
                reason = '{reason}'
            WHERE pt_contract_id = {pt_contract_id}
            AND reservation_id = '{reservation_id}'
            AND status = 'SCHEDULED'
            RETURNING start_time;
            """
            
            update_result = execute_query(update_query)
            
            if update_result and update_result != "데이터가 없습니다.":
                # 새 예약 추가
                insert_query = f"""
                INSERT INTO pt_schedule (start_time, end_time, pt_contract_id, status)
                VALUES ('{start_dt}', '{end_dt}', 7, 'SCHEDULED')
                RETURNING reservation_id;
                """
                
                new_result = execute_query(insert_query)
                
                if new_result and new_result != "데이터가 없습니다.":
                    try:
                        # 결과가 튜플 리스트인 경우 처리
                        if isinstance(new_result, list) and len(new_result) > 0 and isinstance(new_result[0], tuple) and len(new_result[0]) > 0:
                            new_reservation_id = new_result[0][0]
                        else:
                            new_reservation_id = new_result
                            
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
                        
                        response = {
                            "success": True,
                            "action": "change",
                            "old_schedule": {
                                "reservation_id": reservation_id,
                                "start_time": old_date_str
                            },
                            "new_schedule": {
                                "reservation_id": new_reservation_id,
                                "start_time": new_date_str,
                                "reason": reason
                            }
                        }

                        return json.dumps(response, ensure_ascii=False)
                    except Exception as e:

                        return json.dumps({
                            "success": False,
                            "error": f"예약 변경 중 오류가 발생했습니다: {str(e)}"
                        }, ensure_ascii=False)
                else:
                    return json.dumps({
                        "success": False,
                        "error": "새 예약 추가에 실패했습니다."
                    }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": "예약 상태 변경에 실패했습니다."
                }, ensure_ascii=False)
        
        return json.dumps({
            "success": False,
            "error": "잘못된 작업입니다. 'cancel' 또는 'change'를 입력해주세요."
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"예약 처리 중 오류가 발생했어요: {str(e)}"
        }, ensure_ascii=False) 