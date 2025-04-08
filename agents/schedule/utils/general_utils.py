import ast
from datetime import datetime
from utils.logger import log_function_call, log_error
import traceback

@log_function_call
def format_schedule_result(result_str: str) -> str:
    """일정 조회 결과를 포맷팅합니다.
    
    Args:
        result_str: 포맷팅할 결과 문자열
        
    Returns:
        str: 포맷팅된 결과 문자열
    """
    try:
        # 결과가 문자열인 경우 그대로 반환
        if result_str == "데이터가 없습니다.":
            return "예약된 일정이 없습니다."
            
        # 결과가 리스트인 경우 처리
        if result_str.startswith("[") and result_str.endswith("]"):
            # 문자열을 파이썬 객체로 변환
            result_list = ast.literal_eval(result_str)
            
            if not result_list:
                return "예약된 일정이 없습니다."
                
            formatted_result = "예약된 일정이에요.\n"
            for i, item in enumerate(result_list, 1):
                if isinstance(item, tuple) and len(item) >= 2:
                    start_time = item[0]
                    reservation_no = item[1]
                    
                    # datetime 객체 처리
                    if hasattr(start_time, 'strftime'):
                        formatted_date = start_time.strftime("%Y년 %m월 %d일 %H시 %M분")
                    else:
                        formatted_date = str(start_time)
                        
                    formatted_result += f"{i}. {formatted_date} (예약번호: {reservation_no})\n"
                else:
                    formatted_result += f"{i}. {str(item)}\n"
                    
            return formatted_result
            
        return result_str
    except Exception as e:
        log_error(f"일정 포맷팅 중 오류 발생: {str(e)}", error_type=type(e).__name__, stack_trace=traceback.format_exc())
        return f"일정 포맷팅 중 오류가 발생했습니다: {str(e)}"

@log_function_call
def format_schedule_result(result: str, start_dt: datetime, end_dt: datetime) -> str:
    """예약 결과를 읽기 쉬운 형식으로 변환합니다.
    
    Args:
        result: 예약 결과 문자열
        start_dt: 시작 시간
        end_dt: 종료 시간
        
    Returns:
        str: 포맷팅된 예약 결과 문자열
    """
    try:
        # 결과가 문자열인 경우 처리
        if result == "데이터가 없습니다.":
            return "예약 생성에 실패했습니다."
            
        # 결과가 리스트인 경우 처리
        if result.startswith("[") and result.endswith("]"):
            # 문자열을 파이썬 객체로 변환
            result_list = ast.literal_eval(result)
            
            if not result_list:
                return "예약 생성에 실패했습니다."
                
            # 예약 번호 추출
            reservation_no = None
            if isinstance(result_list[0], tuple) and len(result_list[0]) > 0:
                reservation_no = result_list[0][0]
            else:
                reservation_no = result_list[0]
                
            # 날짜 포맷팅
            if hasattr(start_dt, 'strftime'):
                formatted_start = start_dt.strftime("%Y년 %m월 %d일 %H시 %M분")
            else:
                formatted_start = str(start_dt)
                
            if hasattr(end_dt, 'strftime'):
                formatted_end = end_dt.strftime("%Y년 %m월 %d일 %H시 %M분")
            else:
                formatted_end = str(end_dt)
                
            return (
                f"예약이 성공적으로 생성되었습니다.\n\n"
                f"예약 번호: {reservation_no}\n"
                f"시작 시간: {formatted_start}\n"
                f"종료 시간: {formatted_end}"
            )
            
        return result
    except Exception as e:
        log_error(f"예약 결과 포맷팅 중 오류 발생: {str(e)}", error_type=type(e).__name__, stack_trace=traceback.format_exc())
        return f"예약 결과 포맷팅 중 오류가 발생했습니다: {str(e)}"