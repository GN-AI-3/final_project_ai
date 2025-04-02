import datetime
from langchain.agents import tool
from database import db

@tool
def get_schema():
    """ helper 1 """
    return db.get_table_info()
    
@tool
def run_query(query):
    """ helper 2 """
    try:
        result = db.run(query)
        if not result or result.strip() == "":
            return "데이터가 없습니다."
        return result
    except Exception as e:
        return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"

@tool
def get_user_names():
    """데이터베이스에서 사용자 이름 목록을 가져옵니다."""
    try:
        query = "SELECT name FROM users;"
        result = db.run(query)
        
        if result and result.strip() != "":
            # 결과를 리스트로 변환
            # eval을 사용하여 문자열을 파이썬 리스트로 변환
            result_list = eval(result)
            # 튜플에서 첫 번째 요소(이름)만 추출
            names = [item[0] for item in result_list]
            return names
        print("결과가 비어있습니다.")
        return []
    except Exception as e:
        print(f"사용자 목록 조회 중 오류 발생: {str(e)}")
        print("=== get_user_names 종료 ===\n")
        return []

@tool
def extract_name(text: str) -> str:
    """사용자 입력에서 이름을 추출합니다."""

    # 데이터베이스에서 사용자 이름 목록 가져오기
    user_names = get_user_names.invoke(input="")
    print(f"사용 가능한 이름 목록: {user_names}")
    
    # 입력 텍스트에서 각 이름이 포함되어 있는지 확인
    for name in user_names:
        if name in text:
            return name
    return ""

@tool
def format_datetime(dt_str: str) -> str:
    """datetime 문자열을 읽기 쉬운 형식으로 변환합니다."""
    try:
        # 문자열에서 datetime 객체 추출
        dt = eval(dt_str)  # 문자열을 datetime 객체로 변환
        return f"{dt.year}년 {dt.month}월 {dt.day}일 {dt.hour}시 {dt.minute}분"
    except:
        return dt_str

@tool
def format_schedule_result(result: str) -> str:
    """예약 결과를 읽기 쉬운 형식으로 변환합니다."""
    try:
        # 결과 문자열을 리스트로 변환
        schedule_list = eval(result)
        if not schedule_list:
            return "예약된 일정이 없습니다."
        
        formatted_schedules = []
        for start_time, end_time, trainer_name in schedule_list:
            # datetime 객체를 문자열로 변환
            if isinstance(start_time, datetime.datetime):
                start = start_time.strftime("%Y년 %m월 %d일 %H시 %M분")
            else:
                # 문자열로 된 datetime 객체를 파싱
                start = start_time.strftime("%Y년 %m월 %d일 %H시 %M분")
            formatted_schedules.append(f"{start}에 {trainer_name} 선생님과 운동 예정이에요.")
        
        return "\n".join(formatted_schedules)
    except Exception as e:
        print(f"예약 결과 변환 중 오류 발생: {str(e)}")
        return result

@tool
def get_user_schedule(name: str) -> str:
    """사용자의 예약 일정을 조회합니다."""
    try:
        query = f"""
        SELECT r.start_time, r.end_time, u.name as trainer_name
        FROM reservations r
        JOIN users u ON r.trainer_id = u.user_id
        WHERE r.user_id = (SELECT user_id FROM users WHERE name = '{name}')
        ORDER BY r.start_time;
        """
        result = run_query.invoke(input=query)
        if result and result != "데이터가 없습니다.":
            formatted_result = format_schedule_result.invoke(input=result)
            return f"{name}님의 예약 일정입니다:\n{formatted_result}"
        return f"{name}님의 예약된 일정이 없습니다."
    except Exception as e:
        return f"예약 조회 중 오류가 발생했습니다: {str(e)}"

tools = [get_schema, run_query, get_user_names, extract_name, format_datetime, format_schedule_result, get_user_schedule] 