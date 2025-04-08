import logging
import time
import functools
import traceback
import json
from datetime import datetime

# 로거 설정
logger = logging.getLogger('schedule_agent')
logger.setLevel(logging.DEBUG)

# 파일 핸들러 설정
file_handler = logging.FileHandler('schedule_agent.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# 콘솔 핸들러 설정
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 포맷터 설정
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 핸들러 추가
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_function_call(func):
    """함수 호출을 로깅하는 데코레이터"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        # 함수 호출 정보 로깅
        logger.debug(f"함수 호출: {func_name}")
        logger.debug(f"인자: args={args}, kwargs={kwargs}")
        
        try:
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 실행 시간 계산
            execution_time = time.time() - start_time
            
            # 결과 로깅
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)
                
            logger.debug(f"함수 결과: {func_name} - {result_str}")
            logger.debug(f"실행 시간: {func_name} - {execution_time:.4f}초")
            
            return result
        except Exception as e:
            # 예외 로깅
            logger.error(f"함수 오류: {func_name} - {str(e)}")
            logger.error(f"스택 트레이스: {traceback.format_exc()}")
            raise
    return wrapper

def log_sql_query(query, params=None):
    """SQL 쿼리 로깅"""
    logger.debug(f"SQL 쿼리: {query}")
    if params:
        logger.debug(f"SQL 파라미터: {params}")

def log_api_request(endpoint, method, request_data=None):
    """API 요청 로깅"""
    logger.debug(f"API 요청: {method} {endpoint}")
    if request_data:
        logger.debug(f"요청 데이터: {json.dumps(request_data, ensure_ascii=False)}")

def log_api_response(endpoint, response_data, status_code=None):
    """API 응답 로깅"""
    logger.debug(f"API 응답: {endpoint}")
    if status_code:
        logger.debug(f"상태 코드: {status_code}")
    if response_data:
        logger.debug(f"응답 데이터: {json.dumps(response_data, ensure_ascii=False)}")

def log_schedule_action(action, reservation_no, details=None):
    """예약 관련 액션 로깅"""
    logger.info(f"예약 액션: {action} - 예약번호: {reservation_no}")
    if details:
        logger.debug(f"상세 정보: {json.dumps(details, ensure_ascii=False)}")

def log_error(error_message, error_type=None, stack_trace=None):
    """오류 로깅"""
    logger.error(f"오류 발생: {error_message}")
    if error_type:
        logger.error(f"오류 유형: {error_type}")
    if stack_trace:
        logger.error(f"스택 트레이스: {stack_trace}")

def log_user_interaction(user_id, action, input_data=None, response_data=None):
    """사용자 상호작용 로깅"""
    logger.info(f"사용자 상호작용: {user_id} - {action}")
    if input_data:
        logger.debug(f"입력 데이터: {json.dumps(input_data, ensure_ascii=False)}")
    if response_data:
        logger.debug(f"응답 데이터: {json.dumps(response_data, ensure_ascii=False)}") 