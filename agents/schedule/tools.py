import datetime
from typing import List, Tuple

from langchain.agents import tool

from database import db


@tool
def get_schema():
    """데이터베이스 스키마 정보를 반환합니다."""
    return db.get_table_info()
    

@tool
def run_query(query: str) -> str:
    """SQL 쿼리를 실행하고 결과를 반환합니다."""
    try:
        result = db.run(query)
        if not result or result.strip() == "":
            return "데이터가 없습니다."
        return result
    except Exception as e:
        return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"


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
        for start_time, end_time, _ in schedule_list:
            # datetime 객체를 문자열로 변환
            if isinstance(start_time, datetime.datetime):
                start = start_time.strftime("%Y년 %m월 %d일 %H시 %M분")
            else:
                # 문자열로 된 datetime 객체를 파싱
                start = start_time.strftime("%Y년 %m월 %d일 %H시 %M분")
            formatted_schedules.append(f"{start}에 예약이 있습니다.")
        
        return "\n".join(formatted_schedules)
    except Exception as e:
        print(f"예약 결과 변환 중 오류 발생: {str(e)}")
        return result


@tool
def get_user_schedule(pt_linked_id: str) -> str:
    """사용자의 예약 일정을 조회합니다."""
    try:
        query = f"""
        SELECT r.start_time, r.end_time, r.state
        FROM reservations r
        WHERE r.pt_linked_id = {pt_linked_id}
        AND r.start_time > CURRENT_TIMESTAMP
        ORDER BY r.start_time;
        """
        result = run_query.invoke(input=query)
        if result and result != "데이터가 없습니다.":
            formatted_result = format_schedule_result.invoke(input=result)
            return f"예약 일정입니다:\n{formatted_result}"
        return "예약된 일정이 없습니다."
    except Exception as e:
        return f"예약 조회 중 오류가 발생했습니다: {str(e)}"


tools = [
    get_schema,
    run_query,
    format_datetime,
    format_schedule_result,
    get_user_schedule
] 