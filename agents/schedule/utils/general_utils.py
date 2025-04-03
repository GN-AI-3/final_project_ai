import random
import string
import datetime

def generate_reservation_no() -> str:
    """예약 번호를 생성합니다."""
    created_date = datetime.datetime.now().strftime("%y%m%d")
    random_digits = ''.join(random.choices(string.digits, k=5))
    return f"{created_date}_{random_digits}"

def format_schedule_result(result: str) -> str:
    """예약 결과를 읽기 쉬운 형식으로 변환합니다."""
    try:
        # 결과 문자열을 리스트로 변환
        schedule_list = eval(result)
        if not schedule_list:
            return "아직 예약된 일정이 없어요. 새로운 예약을 만들어보시는 건 어떨까요?"
        
        formatted_schedules = []
        for idx, (start_time, reservation_no) in enumerate(schedule_list, 1):
            # datetime 객체에서 시간 정보 추출
            dt = start_time
            year = dt.year
            month = str(dt.month).zfill(2)
            day = str(dt.day).zfill(2)
            hour = dt.hour
            minute = str(dt.minute).zfill(2)
            
            # 오전/오후 구분
            ampm = "오전" if hour < 12 else "오후"
            hour_12 = hour if hour <= 12 else hour - 12
            
            formatted_time = f"{year}년 {month}월 {day}일 {ampm} {hour_12}시 {minute}분"
            formatted_schedules.append(f"{idx}. {formatted_time} (예약번호: {reservation_no})")
        
        return "예약된 일정이에요.\n" + "\n".join(formatted_schedules)
    except Exception as e:
        print(f"예약 결과를 변환하는 중에 오류가 발생했어요: {str(e)}")
        return result 