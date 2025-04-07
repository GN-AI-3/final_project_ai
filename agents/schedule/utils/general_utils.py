import datetime

def format_schedule_result(result: str) -> str:
    """예약 결과를 읽기 쉬운 형식으로 변환합니다."""
    try:
        # 결과 문자열을 리스트로 변환
        schedule_list = eval(result)
        if not schedule_list:
            return "아직 예약된 일정이 없어요. 새로운 예약을 만들어보시는 건 어떨까요?"
        
        formatted_schedules = []
        for idx, (start_time, reservation_no) in enumerate(schedule_list, 1):
            # datetime 객체 또는 문자열인 경우 처리
            if isinstance(start_time, str):
                try:
                    # 문자열을 datetime 객체로 변환
                    start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # 변환 실패시 원래 문자열 사용
                    pass
            
            # datetime 객체에서 시간 정보 추출
            if hasattr(start_time, 'year'):
                year = start_time.year
                month = str(start_time.month).zfill(2)
                day = str(start_time.day).zfill(2)
                hour = start_time.hour
                minute = str(start_time.minute).zfill(2)
                
                # 오전/오후 구분
                ampm = "오전" if hour < 12 else "오후"
                hour_12 = hour if hour <= 12 else hour - 12
                
                formatted_time = f"{year}년 {month}월 {day}일 {ampm} {hour_12}시 {minute}분"
            else:
                # datetime 객체가 아닌 경우 원래 문자열 사용
                formatted_time = str(start_time)
            
            formatted_schedules.append(f"{idx}. {formatted_time} (예약번호: {reservation_no})")
        
        return "예약된 일정이에요.\n" + "\n".join(formatted_schedules)
    except Exception as e:
        return result

def format_reservation_result(result: str, start_dt: datetime, end_dt: datetime) -> str:
    """예약 추가 결과를 읽기 쉬운 형식으로 변환합니다."""
    try:
        if result and "error" not in result.lower():
            parsed_result = eval(result)
            if parsed_result:
                reservation_no = parsed_result[0][0]
                return f"예약이 성공적으로 추가되었습니다. 예약 번호: {reservation_no}, 시간: {start_dt.strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {end_dt.strftime('%H시 %M분')}"
        return f"예약 추가 중 오류가 발생했습니다: {result}"
    except Exception as e:
        return f"예약 처리 중 오류가 발생했어요: {str(e)}"