from datetime import datetime
from typing import Optional, Dict
import json
import httpx
import os
import jwt
import re

from langchain.agents import tool

from ..utils.date_utils import validate_date_format, parse_relative_date
from ..core.database import execute_query

# API 기본 URL 설정 - 환경 변수 사용
API_BASE_URL = os.getenv("EC2_BACKEND_URL") + "/api"
# 인증 토큰 설정
AUTH_TOKEN = os.getenv(
    "AUTH_TOKEN",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzM4NCJ9.eyJwYXNzd29yZCI6IiQyYSQxMCRkNEhjZUNXc1VnL2FUdzQ2am14bDV1SHVwV0h4YjdIeWpTVmUuRzlXSi5LeXdoMkRQVmVyRyIsInBob25lIjoiMDEwLTExMTEtMjIyMiIsIm5hbWUiOiLsnqXqt7zsmrAiLCJpZCI6NCwidXNlclR5cGUiOiJNRU1CRVIiLCJlbWFpbCI6InVzZXIxQHRlc3QuY29tIiwiZ29hbHMiOlsiV0VJR0hUX0xPU1MiXSwiaWF0IjoxNzQ1MDUyMzE5LCJleHAiOjM2MzcyMTIzMTl9._Y1TZGQOGPZDLB4YdYX-21TN1bv_aYBuxX9N_EvY6y_QADh2hLJDEyUKIIGXuc4i"
)

def get_pt_contract_id_from_token(token: str) -> tuple[int, int]:
    """JWT 토큰에서 member_id와 user_type을 추출하고 해당 member의 pt_contract_id를 찾습니다.
    
    Args:
        token (str): JWT 토큰
        
    Returns:
        tuple[int, int]: (pt_contract_id, trainer_id), 추출 실패 시 (0, 0)
    """
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        member_id = decoded.get("id", 0)
        user_type = decoded.get("userType", "")
        
        if member_id == 0:
            return (0, 0)
            
        # member_id로 pt_contract_id 찾기
        contract_query = f"""
            SELECT id, trainer_id
            FROM pt_contract
            WHERE member_id = {member_id}
            LIMIT 1;
        """
        
        contract_result = execute_query(contract_query)
        
        if not contract_result or contract_result == "데이터가 없습니다.":
            return (0, 0)
            
        # 문자열에서 숫자만 추출
        if isinstance(contract_result, str):
            # 괄호 안의 숫자만 추출
            numbers = re.findall(r'\d+', contract_result)
            if len(numbers) >= 2:
                return (int(numbers[0]), int(numbers[1]))
        
        return (0, 0)
        
    except Exception:
        return (0, 0)

def make_api_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
    """API 요청을 보내는 헬퍼 함수.
    
    Args:
        endpoint (str): API 엔드포인트
        method (str, optional): HTTP 메소드. 기본값은 "GET"
        data (Optional[Dict], optional): 요청 데이터. 기본값은 None
        
    Returns:
        Dict: API 응답 데이터
    """
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = httpx.get(url, headers=headers)
        elif method == "POST":
            response = httpx.post(url, json=data, headers=headers)
        elif method == "PUT":
            response = httpx.put(url, json=data, headers=headers)
        elif method == "DELETE":
            response = httpx.delete(url, headers=headers)
        elif method == "PATCH":
            response = httpx.patch(url, json=data, headers=headers)
        else:
            raise ValueError(f"지원하지 않는 HTTP 메서드입니다: {method}")
        
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API 요청 중 오류가 발생했습니다: {str(e)}"
        }

def check_future_date(start_dt: datetime) -> str:
    """미래 날짜 여부를 확인합니다.
    
    Args:
        start_dt (datetime): 확인할 날짜
        
    Returns:
        str: 과거 날짜인 경우 에러 메시지, 미래 날짜인 경우 None
    """
    try:
        now = datetime.now()
        
        # 날짜만 비교 (시간 제외)
        if (start_dt.year < now.year or
            (start_dt.year == now.year and start_dt.month < now.month) or
            (start_dt.year == now.year and start_dt.month == now.month and start_dt.day < now.day)):
            return (
                "죄송해요. 과거 날짜로는 예약할 수 없어요. "
                "오늘 이후의 날짜를 선택해주세요."
            )
        return None
    except Exception as e:
        return f"미래 날짜 확인 중 오류가 발생했습니다: {str(e)}"

def check_existing_schedule(start_dt: datetime, end_dt: datetime) -> str:
    """해당 시간대에 이미 예약이 있는지 확인합니다.
    
    Args:
        start_dt (datetime): 예약 시작 시간
        end_dt (datetime): 예약 종료 시간
        
    Returns:
        str: 중복 예약이 있는 경우 에러 메시지, 없는 경우 None
    """
    try:
        print("[DEBUG] check_existing_schedule 함수 시작")
        print(f"[DEBUG] 입력된 시간 - 시작: {start_dt}, 종료: {end_dt}")
        
        # pt_contract_id로 trainer_id 찾기
        pt_contract_id, trainer_id = get_pt_contract_id_from_token(AUTH_TOKEN)
        print(f"[DEBUG] 토큰에서 추출한 pt_contract_id: {pt_contract_id}, trainer_id: {trainer_id}")
        
        if pt_contract_id == 0:
            print("[DEBUG] pt_contract_id가 0입니다")
            return "트레이너 정보를 찾을 수 없습니다."
            
        trainer_query = f"""
            SELECT trainer_id
            FROM pt_contract
            WHERE id = {pt_contract_id}
            LIMIT 1;
        """
        print(f"[DEBUG] trainer_id 조회 쿼리: {trainer_query}")
        
        trainer_result = execute_query(trainer_query)
        print(f"[DEBUG] trainer_id 조회 결과: {trainer_result}")
        
        if not trainer_result or trainer_result == "데이터가 없습니다.":
            print("[DEBUG] trainer_result가 없거나 '데이터가 없습니다'")
            return "트레이너 정보를 찾을 수 없습니다."
            
        # 문자열에서 숫자만 추출
        if isinstance(trainer_result, str):
            # 괄호 안의 숫자만 추출
            numbers = re.findall(r'\d+', trainer_result)
            if numbers:
                trainer_id = int(numbers[0])
                print(f"[DEBUG] 추출된 trainer_id: {trainer_id}")
            else:
                print("[DEBUG] trainer_result에서 숫자를 추출할 수 없습니다")
                return "트레이너 정보를 찾을 수 없습니다."
        else:
            print("[DEBUG] trainer_result가 문자열이 아님")
            return "트레이너 정보를 찾을 수 없습니다."
        
        start_time_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[DEBUG] 검색할 시간 범위 - 시작: {start_time_str}, 종료: {end_time_str}")
        
        check_query = f"""
            SELECT start_time, end_time
            FROM pt_schedule
            WHERE pt_contract_id IN (
                SELECT id 
                FROM pt_contract 
                WHERE trainer_id = {trainer_id}
            )
            AND status = 'scheduled'
            AND NOT (
                end_time <= '{start_time_str}' OR
                start_time >= '{end_time_str}'
            )
            LIMIT 1;
        """
        print(f"[DEBUG] 중복 예약 확인 쿼리: {check_query}")
        
        result = execute_query(check_query)
        print(f"[DEBUG] 중복 예약 확인 결과: {result}")
        
        # 결과가 없거나 "데이터가 없습니다"인 경우
        if not result or result == "데이터가 없습니다.":
            print("[DEBUG] 중복 예약이 없음")
            return None
        
        # 결과가 문자열인 경우
        if isinstance(result, str):
            # 괄호 안의 날짜/시간 정보 추출
            datetime_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
            datetimes = re.findall(datetime_pattern, result)
            if len(datetimes) >= 2:
                existing_start = datetime.strptime(datetimes[0], '%Y-%m-%d %H:%M:%S')
                existing_end = datetime.strptime(datetimes[1], '%Y-%m-%d %H:%M:%S')
                print(f"[DEBUG] 중복 예약 시간 - 시작: {existing_start}, 종료: {existing_end}")
                
                start_str = existing_start.strftime('%Y-%m-%d %H:%M')
                end_str = existing_end.strftime('%H:%M')
                return (
                    f"죄송해요. 해당 시간대({start_str} ~ {end_str})에 "
                    "이미 예약이 있어요. 다른 시간으로 예약해보시는 건 어떨까요?"
                )
            print("[DEBUG] 중복 예약 시간 정보 추출 실패")
            return (
                "죄송해요. 해당 시간대에 이미 예약이 있어요. "
                "다른 시간으로 예약해보시는 건 어떨까요?"
            )
        
        print("[DEBUG] 중복 예약이 없음")
        return None
        
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {str(e)}")
        return f"예약 중복 확인 중 오류가 발생했습니다: {str(e)}"

@tool
def get_user_schedule(input: str = "") -> str:
    """사용자의 스케줄을 조회합니다.
    
    Args:
        input (str, optional): 날짜 범위를 나타내는 자연어 (예: "오늘", "이번 주", "다음 주"). 기본값은 ""
        
    Returns:
        str: JSON 형식의 스케줄 정보
    """
    try:
        print(f"[DEBUG] get_user_schedule 시작 - 입력: {input}")
        
        # 토큰에서 user_type 추출
        decoded = jwt.decode(AUTH_TOKEN, options={"verify_signature": False})
        user_type = decoded.get("userType", "")
        print(f"[DEBUG] 사용자 타입: {user_type}")
        
        # 트레이너인 경우 get_trainer_schedule 함수 사용
        if user_type == "TRAINER":
            print("[DEBUG] 트레이너로 확인됨 - get_trainer_schedule 함수 호출")
            return get_trainer_schedule(input)
            
        # 전체 일정 조회
        schedules = make_api_request("pt_schedules")
        print(f"[DEBUG] 전체 일정 조회 결과: {schedules}")
        
        # 상대적인 날짜 처리
        target_date_range = parse_relative_date(input)
        print(f"[DEBUG] 상대적 날짜 파싱 결과: {target_date_range}")
        
        # SCHEDULED 상태의 일정만 필터링
        scheduled_schedules = []
        for schedule in schedules:
            if schedule.get("status") == "SCHEDULED":
                try:
                    # Unix timestamp를 datetime으로 변환
                    start_time = datetime.fromtimestamp(schedule.get("startTime"))
                    
                    # 날짜 범위 내의 일정만 포함
                    if target_date_range and all(target_date_range):
                        # target_date_range가 정수인 경우 datetime으로 변환
                        start_dt = datetime(target_date_range[0], target_date_range[1], target_date_range[2])
                        end_dt = datetime(target_date_range[3], target_date_range[4], target_date_range[5])
                        if start_dt.date() <= start_time.date() <= end_dt.date():
                            scheduled_schedules.append(schedule)
                    else:
                        scheduled_schedules.append(schedule)
                except (TypeError, ValueError) as e:
                    print(f"[DEBUG] 일정 시간 변환 오류: {str(e)}")
                    continue
        
        print(f"[DEBUG] 필터링된 일정 수: {len(scheduled_schedules)}")
        
        # 일정을 날짜 순으로 정렬
        scheduled_schedules.sort(key=lambda x: x.get("startTime", 0))
        
        formatted_schedules = []
        for schedule in scheduled_schedules:
            try:
                start_time = datetime.fromtimestamp(schedule.get("startTime"))
                
                formatted_schedule = {
                    "reservationId": schedule.get("reservationId"),
                    "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M")
                }
                formatted_schedules.append(formatted_schedule)
            except (TypeError, ValueError) as e:
                print(f"[DEBUG] 일정 포맷팅 오류: {str(e)}")
                continue
        
        return json.dumps({
            "success": True,
            "schedules": formatted_schedules
        }, ensure_ascii=False)
        
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"일정 조회 중 오류가 발생했습니다: {str(e)}"
        }, ensure_ascii=False)


@tool
def add_schedule(day: str, hour: str, month: Optional[str] = None) -> str:
    """스케줄을 추가합니다.
    
    Args:
        day (str): 예약 날짜
        hour (str): 예약 시간
        month (Optional[str], optional): 예약 월. 기본값은 None
        
    Returns:
        str: JSON 형식의 예약 결과
    """
    try:
        month_str = str(month) if month is not None else None
        start_dt, end_dt = validate_date_format(day, hour, month_str)
        
        if start_dt is None:
            return json.dumps({
                "success": False,
                "error": end_dt
            }, ensure_ascii=False)

        error = check_future_date(start_dt)
        if error:
            return json.dumps({
                "success": False,
                "error": error
            }, ensure_ascii=False)

        error = check_existing_schedule(start_dt, end_dt)
        if error:
            return json.dumps({
                "success": False,
                "error": error
            }, ensure_ascii=False)

        # 토큰에서 ptContractId 추출
        pt_contract_id, trainer_id = get_pt_contract_id_from_token(AUTH_TOKEN)
        if pt_contract_id == 0:
            return json.dumps({
                "success": False,
                "error": "유효하지 않은 토큰입니다."
            }, ensure_ascii=False)

        schedule_data = {
            "ptContractId": pt_contract_id,
            "startTime": int(start_dt.timestamp()),
            "endTime": int(end_dt.timestamp())
        }

        response = make_api_request("pt_schedules", "POST", schedule_data)
        
        if not isinstance(response, dict):
            return json.dumps({
                "success": False,
                "error": "예약 추가에 실패했습니다."
            }, ensure_ascii=False)
            
        # API 응답에 success 필드가 없으면 성공으로 간주
        if response.get("success") is False:
            return json.dumps({
                "success": False,
                "error": response.get("error", "예약 추가에 실패했습니다.")
            }, ensure_ascii=False)
            
        # 응답에 reservationId가 있으면 성공으로 간주
        if "reservationId" in response:
            try:
                # Unix timestamp를 datetime으로 변환
                start_time = datetime.fromtimestamp(response.get("startTime"))
                end_time = datetime.fromtimestamp(response.get("endTime"))
                
                formatted_schedule = {
                    "reservationId": response.get("reservationId"),
                    "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M"),
                    "endTime": end_time.strftime("%H:%M")
                }
                
                return json.dumps({
                    "success": True,
                    "schedule": formatted_schedule
                }, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                return json.dumps({
                    "success": False,
                    "error": f"예약 데이터 처리 중 오류가 발생했습니다: {str(e)}"
                }, ensure_ascii=False)
        
        return json.dumps({
            "success": False,
            "error": "예약 추가에 실패했습니다."
        }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"예약 처리 중 오류가 발생했어요: {str(e)}"
        }, ensure_ascii=False)

@tool
def modify_schedule(
    day: str,
    hour: str,
    action: str,
    new_day: Optional[str] = None,
    new_hour: Optional[str] = None,
    new_month: Optional[str] = None,
    reason: Optional[str] = None
) -> str:
    """예약을 취소하거나 변경합니다.
    
    Args:
        day (str): 현재 예약 날짜
        hour (str): 현재 예약 시간
        action (str): 수행할 작업 ('cancel' 또는 'change')
        new_day (Optional[str], optional): 새 예약 날짜. 기본값은 None
        new_hour (Optional[str], optional): 새 예약 시간. 기본값은 None
        new_month (Optional[str], optional): 새 예약 월. 기본값은 None
        reason (Optional[str], optional): 취소/변경 사유. 기본값은 None
        
    Returns:
        str: JSON 형식의 예약 수정 결과
    """
    try:
        print(f"[DEBUG] 함수 시작 - 입력 파라미터:")
        print(f"  - day: {day}")
        print(f"  - hour: {hour}")
        print(f"  - action: {action}")
        print(f"  - new_day: {new_day}")
        print(f"  - new_hour: {new_hour}")
        print(f"  - new_month: {new_month}")
        print(f"  - reason: {reason}")
        
        # 전체 일정 조회
        print("[DEBUG] 전체 일정 조회 시작")
        all_schedules_response = make_api_request("pt_schedules")
        print(f"[DEBUG] 전체 일정 조회 결과: {all_schedules_response}")
        
        # API 응답이 리스트인 경우 직접 사용
        if isinstance(all_schedules_response, list):
            schedules = all_schedules_response
        else:
            schedules = all_schedules_response.get("data", [])
        print(f"[DEBUG] 파싱된 schedules: {schedules}")
        
        if not isinstance(schedules, list):
            print("[DEBUG] schedules가 list가 아님")
            return json.dumps({
                "success": False,
                "error": "일정 데이터 형식이 올바르지 않습니다."
            }, ensure_ascii=False)
        
        # SCHEDULED 상태의 일정만 필터링
        print("[DEBUG] SCHEDULED 상태의 일정 필터링 시작")
        scheduled_schedules = []
        for s in schedules:
            if isinstance(s, dict) and s.get("status") == "SCHEDULED":
                scheduled_schedules.append(s)
        print(f"[DEBUG] 필터링된 scheduled_schedules: {scheduled_schedules}")
        
        # 입력된 날짜와 시간으로 일정 찾기
        print("[DEBUG] 대상 일정 찾기 시작")
        target_schedule = None
        try:
            # 날짜와 시간을 파싱 (한글 형식과 YYYY-MM-DD 형식 모두 지원)
            try:
                # 먼저 YYYY-MM-DD 형식 시도
                print(f"[DEBUG] YYYY-MM-DD 형식으로 날짜 파싱 시도: {day}")
                target_date = datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                # YYYY-MM-DD 형식 실패 시 한글 형식 시도
                print(f"[DEBUG] 한글 형식으로 날짜 파싱 시도: {day}")
                target_date = datetime.strptime(day, "%Y년 %m월 %d일")
            
            print(f"[DEBUG] 시간 파싱 시도: {hour}")
            target_time = datetime.strptime(hour, "%H:%M").time()
            target_start_dt = datetime.combine(target_date, target_time)
            print(f"[DEBUG] 최종 target_start_dt: {target_start_dt}")
        except ValueError as e:
            print(f"[DEBUG] 날짜/시간 파싱 오류 발생: {str(e)}")
            return json.dumps({
                "success": False,
                "error": "유효하지 않은 날짜 또는 시간입니다."
            }, ensure_ascii=False)
        
        for schedule in scheduled_schedules:
            try:
                schedule_start_time = datetime.fromtimestamp(schedule.get("startTime"))
                print(f"[DEBUG] schedule_start_time: {schedule_start_time}")
                if schedule_start_time == target_start_dt:
                    target_schedule = schedule
                    print(f"[DEBUG] target_schedule 찾음: {target_schedule}")
                    break
            except (TypeError, ValueError) as e:
                print(f"[DEBUG] schedule_start_time 변환 오류: {str(e)}")
                continue
                
        if not target_schedule:
            print("[DEBUG] target_schedule을 찾을 수 없음")
            return json.dumps({
                "success": False,
                "error": f"{target_start_dt.strftime('%Y년 %m월 %d일 %H:%M')}에 "
                         "해당하는 예약을 찾을 수 없습니다."
            }, ensure_ascii=False)
        
        if not reason or reason.strip() == "":
            print("[DEBUG] reason이 없음")
            if action == "cancel":
                return json.dumps({
                    "success": False,
                    "error": "예약을 취소하려면 취소 사유를 알려주세요."
                }, ensure_ascii=False)
            return json.dumps({
                "success": False,
                "error": "예약을 변경하려면 변경 사유를 알려주세요."
            }, ensure_ascii=False)
        
        if action == "cancel":
            print("[DEBUG] 취소 작업 시작")
            cancel_data = {
                "reason": reason
            }
            print(f"[DEBUG] cancel_data: {cancel_data}")
            
            cancel_response = make_api_request(
                f"pt_schedules/{target_schedule.get('id')}/cancel",
                "PATCH",
                cancel_data
            )
            print(f"[DEBUG] cancel response: {cancel_response}")
            
            if not isinstance(cancel_response, dict):
                print("[DEBUG] cancel response가 dict가 아님")
                return json.dumps({
                    "success": False,
                    "error": "예약 취소에 실패했습니다."
                }, ensure_ascii=False)
                
            if cancel_response.get("success") is False:
                print(f"[DEBUG] cancel API error: {cancel_response.get('error')}")
                return json.dumps({
                    "success": False,
                    "error": cancel_response.get("error", "예약 취소에 실패했습니다.")
                }, ensure_ascii=False)
                
            if "reservationId" in cancel_response:
                try:
                    start_time = datetime.fromtimestamp(cancel_response.get("startTime"))
                    print(f"[DEBUG] cancel success - start_time: {start_time}")
                    
                    return json.dumps({
                        "success": True,
                        "schedule": {
                            "reservationId": cancel_response.get("reservationId"),
                            "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M"),
                            "reason": reason
                        }
                    }, ensure_ascii=False)
                except (TypeError, ValueError) as e:
                    print(f"[DEBUG] cancel timestamp 변환 오류: {str(e)}")
                    return json.dumps({
                        "success": False,
                        "error": f"예약 데이터 처리 중 오류가 발생했습니다: {str(e)}"
                    }, ensure_ascii=False)
        
        elif action == "change":
            print("[DEBUG] 변경 작업 시작")
            try:
                # 새로운 날짜와 시간을 파싱 (한글 형식과 YYYY-MM-DD 형식 모두 지원)
                try:
                    # 먼저 YYYY-MM-DD 형식 시도
                    new_date = datetime.strptime(new_day, "%Y-%m-%d")
                except ValueError:
                    # YYYY-MM-DD 형식 실패 시 한글 형식 시도
                    new_date = datetime.strptime(new_day, "%Y년 %m월 %d일")
                
                # 시간 파싱 (24시간 형식 지원)
                try:
                    new_time = datetime.strptime(new_hour, "%H:%M").time()
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "error": "유효하지 않은 시간 형식입니다."
                    }, ensure_ascii=False)
                
                start_dt = datetime.combine(new_date, new_time)
                end_dt = start_dt.replace(hour=start_dt.hour + 1)  # 1시간 후
                print(f"[DEBUG] new start_dt: {start_dt}, end_dt: {end_dt}")
            except ValueError as e:
                print(f"[DEBUG] 새로운 날짜/시간 파싱 오류: {str(e)}")
                return json.dumps({
                    "success": False,
                    "error": "유효하지 않은 날짜 또는 시간입니다."
                }, ensure_ascii=False)
            
            error = check_future_date(start_dt)
            if error:
                print(f"[DEBUG] future date check error: {error}")
                return json.dumps({
                    "success": False,
                    "error": error
                }, ensure_ascii=False)
            
            error = check_existing_schedule(start_dt, end_dt)
            if error:
                print(f"[DEBUG] existing schedule check error: {error}")
                return json.dumps({
                    "success": False,
                    "error": error
                }, ensure_ascii=False)
            
            change_data = {
                "startTime": int(start_dt.timestamp()),
                "endTime": int(end_dt.timestamp()),
                "reason": reason
            }
            print(f"[DEBUG] change_data: {change_data}")
            
            change_response = make_api_request(
                f"pt_schedules/{target_schedule.get('id')}/change",
                "PATCH",
                change_data
            )
            print(f"[DEBUG] change response: {change_response}")
            
            if not isinstance(change_response, dict):
                print("[DEBUG] change response가 dict가 아님")
                return json.dumps({
                    "success": False,
                    "error": "예약 변경에 실패했습니다."
                }, ensure_ascii=False)
                
            if change_response.get("success") is False:
                print(f"[DEBUG] change API error: {change_response.get('error')}")
                return json.dumps({
                    "success": False,
                    "error": change_response.get("error", "예약 변경에 실패했습니다.")
                }, ensure_ascii=False)
                
            if "reservationId" in change_response:
                try:
                    start_time = datetime.fromtimestamp(change_response.get("startTime"))
                    end_time = datetime.fromtimestamp(change_response.get("endTime"))
                    print(f"[DEBUG] change success - start_time: {start_time}, end_time: {end_time}")
                    
                    return json.dumps({
                        "success": True,
                        "schedule": {
                            "reservationId": change_response.get("reservationId"),
                            "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M"),
                            "endTime": end_time.strftime("%H:%M"),
                            "reason": reason
                        }
                    }, ensure_ascii=False)
                except (TypeError, ValueError) as e:
                    print(f"[DEBUG] change timestamp 변환 오류: {str(e)}")
                    return json.dumps({
                        "success": False,
                        "error": f"예약 데이터 처리 중 오류가 발생했습니다: {str(e)}"
                    }, ensure_ascii=False)
        
        print("[DEBUG] 잘못된 action")
        return json.dumps({
            "success": False,
            "error": "잘못된 작업입니다. 'cancel' 또는 'change'를 입력해주세요."
        }, ensure_ascii=False)
        
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"예약 처리 중 오류가 발생했어요: {str(e)}"
        }, ensure_ascii=False)

@tool
def get_trainer_schedule(input: str = "") -> str:
    """트레이너의 모든 회원 일정을 조회합니다.
    
    Args:
        input (str, optional): 날짜 범위를 나타내는 자연어 (예: "오늘", "이번 주", "다음 주"). 기본값은 ""
        
    Returns:
        str: JSON 형식의 스케줄 정보
    """
    try:
        print(f"[DEBUG] get_trainer_schedule 시작 - 입력: {input}")
        
        # 토큰에서 trainer_id 추출
        _, trainer_id = get_pt_contract_id_from_token(AUTH_TOKEN)
        if trainer_id == 0:
            return json.dumps({
                "success": False,
                "error": "트레이너 정보를 찾을 수 없습니다."
            }, ensure_ascii=False)
            
        # 상대적인 날짜 처리
        target_date_range = parse_relative_date(input)
        print(f"[DEBUG] 상대적 날짜 파싱 결과: {target_date_range}")
        
        # 트레이너의 모든 회원 일정 조회
        query = f"""
            SELECT 
                ps.reservation_id,
                ps.start_time,
                ps.end_time,
                m.name as member_name
            FROM pt_schedule ps
            JOIN pt_contract pc ON ps.pt_contract_id = pc.id
            JOIN member m ON pc.member_id = m.id
            WHERE pc.trainer_id = {trainer_id}
            AND ps.status = 'scheduled'
        """
        
        if target_date_range and all(target_date_range):
            start_dt = datetime(target_date_range[0], target_date_range[1], target_date_range[2])
            end_dt = datetime(target_date_range[3], target_date_range[4], target_date_range[5])
            query += f"""
                AND ps.start_time >= '{start_dt.strftime('%Y-%m-%d %H:%M:%S')}'
                AND ps.start_time <= '{end_dt.strftime('%Y-%m-%d %H:%M:%S')}'
            """
            
        query += " ORDER BY ps.start_time ASC;"
        
        print(f"[DEBUG] 일정 조회 쿼리: {query}")
        schedules = execute_query(query)
        
        if not schedules or schedules == "데이터가 없습니다.":
            return json.dumps({
                "success": True,
                "schedules": []
            }, ensure_ascii=False)
            
        formatted_schedules = []
        for schedule in schedules:
            try:
                start_time = datetime.fromtimestamp(schedule[1])
                end_time = datetime.fromtimestamp(schedule[2])
                
                formatted_schedule = {
                    "reservationId": schedule[0],
                    "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M"),
                    "endTime": end_time.strftime("%H:%M"),
                    "memberName": schedule[3]
                }
                formatted_schedules.append(formatted_schedule)
            except (TypeError, ValueError) as e:
                print(f"[DEBUG] 일정 포맷팅 오류: {str(e)}")
                continue
        
        return json.dumps({
            "success": True,
            "schedules": formatted_schedules
        }, ensure_ascii=False)
        
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"일정 조회 중 오류가 발생했습니다: {str(e)}"
        }, ensure_ascii=False)

@tool
def get_member_schedule(member_name: str, input: str = "") -> str:
    """트레이너가 특정 회원의 일정을 조회합니다.
    
    Args:
        member_name (str): 회원 이름
        input (str, optional): 날짜 범위를 나타내는 자연어 (예: "오늘", "이번 주", "다음 주"). 기본값은 ""
        
    Returns:
        str: JSON 형식의 스케줄 정보
    """
    try:
        print(f"[DEBUG] ===== get_member_schedule 함수 시작 =====")
        print(f"[DEBUG] 입력 파라미터:")
        print(f"  - member_name: {member_name}")
        print(f"  - input: {input}")
        
        # 토큰에서 trainer_id 추출
        print("[DEBUG] 토큰에서 trainer_id 추출 시도")
        _, trainer_id = get_pt_contract_id_from_token(AUTH_TOKEN)
        print(f"[DEBUG] 추출된 trainer_id: {trainer_id}")
        
        if trainer_id == 0:
            print("[DEBUG] 트레이너 ID 추출 실패")
            return json.dumps({
                "success": False,
                "error": "트레이너 정보를 찾을 수 없습니다."
            }, ensure_ascii=False)
            
        # 상대적인 날짜 처리
        print("[DEBUG] 날짜 범위 파싱 시도")
        target_date_range = parse_relative_date(input)
        print(f"[DEBUG] 파싱된 날짜 범위: {target_date_range}")
        
        # 특정 회원의 일정 조회
        print("[DEBUG] SQL 쿼리 생성 시작")
        query = f"""
            SELECT 
                ps.reservation_id,
                ps.start_time,
                ps.end_time,
                m.name as member_name
            FROM pt_schedule ps
            JOIN pt_contract pc ON ps.pt_contract_id = pc.id
            JOIN member m ON pc.member_id = m.id
            WHERE pc.trainer_id = {trainer_id}
            AND m.name = '{member_name}'
            AND ps.status = 'scheduled'
        """
        
        if target_date_range and all(target_date_range):
            print("[DEBUG] 날짜 범위 조건 추가")
            start_dt = datetime(target_date_range[0], target_date_range[1], target_date_range[2])
            end_dt = datetime(target_date_range[3], target_date_range[4], target_date_range[5])
            query += f"""
                AND ps.start_time >= '{start_dt.strftime('%Y-%m-%d %H:%M:%S')}'
                AND ps.start_time <= '{end_dt.strftime('%Y-%m-%d %H:%M:%S')}'
            """
            print(f"[DEBUG] 추가된 날짜 범위: {start_dt} ~ {end_dt}")
            
        query += " ORDER BY ps.start_time ASC;"
        
        print(f"[DEBUG] 최종 SQL 쿼리:\n{query}")
        print("[DEBUG] 쿼리 실행 시작")
        schedules = execute_query(query)
        print(f"[DEBUG] 쿼리 실행 결과: {schedules}")
        
        if not schedules or schedules == "데이터가 없습니다.":
            print("[DEBUG] 일정 데이터 없음")
            return json.dumps({
                "success": True,
                "schedules": [],
                "message": f"{member_name} 회원님의 예약된 일정이 없습니다."
            }, ensure_ascii=False)
            
        print("[DEBUG] 일정 데이터 포맷팅 시작")
        formatted_schedules = []
        for schedule in schedules:
            try:
                print(f"[DEBUG] 일정 데이터 처리: {schedule}")
                start_time = datetime.fromtimestamp(schedule[1])
                end_time = datetime.fromtimestamp(schedule[2])
                
                formatted_schedule = {
                    "reservationId": schedule[0],
                    "startTime": start_time.strftime("%Y년 %m월 %d일 %H:%M"),
                    "endTime": end_time.strftime("%H:%M"),
                    "memberName": schedule[3]
                }
                print(f"[DEBUG] 포맷팅된 일정: {formatted_schedule}")
                formatted_schedules.append(formatted_schedule)
            except (TypeError, ValueError) as e:
                print(f"[DEBUG] 일정 포맷팅 오류 발생: {str(e)}")
                print(f"[DEBUG] 문제가 발생한 일정 데이터: {schedule}")
                continue
        
        print("[DEBUG] 최종 응답 생성")
        response = json.dumps({
            "success": True,
            "schedules": formatted_schedules,
            "message": f"{member_name} 회원님의 예약된 일정입니다."
        }, ensure_ascii=False)
        print(f"[DEBUG] 생성된 응답: {response}")
        print("[DEBUG] ===== get_member_schedule 함수 종료 =====")
        return response
        
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {str(e)}")
        print(f"[DEBUG] 예외 상세 정보:")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"일정 조회 중 오류가 발생했습니다: {str(e)}"
        }, ensure_ascii=False) 