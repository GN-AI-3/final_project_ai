import datetime

def _parse_relative_date(date_str: str) -> tuple:
    """상대적 날짜 표현을 파싱합니다."""
    now = datetime.datetime.now()
    today = now.date()
    
    # 요일 매핑
    weekdays = {
        '월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6
    }
    
    # 상대적 날짜 매핑
    relative_dates = {
        '오늘': 0,
        '내일': 1,
        '모레': 2,
        '글피': 3,
        '다음주': 7
    }
    
    print(f"디버깅: 상대적 날짜 파싱 시작 - 입력: {date_str}")
    
    try:
        # 기본 상대적 날짜 처리
        if date_str in relative_dates:
            days_to_add = relative_dates[date_str]
            target_date = today + datetime.timedelta(days=days_to_add)
            print(f"디버깅: 기본 상대적 날짜 처리 - {date_str} -> {target_date}")
            return target_date.year, target_date.month, target_date.day
        
        # 다음주 X요일 처리
        if '다음주' in date_str:
            for weekday_kor, weekday_num in weekdays.items():
                if weekday_kor in date_str:
                    days_to_add = 7 + (weekday_num - today.weekday()) % 7
                    target_date = today + datetime.timedelta(days=days_to_add)
                    print(f"디버깅: 다음주 요일 처리 - {date_str} -> {target_date}")
                    return target_date.year, target_date.month, target_date.day
        
        # 이번주 X요일 처리
        for weekday_kor, weekday_num in weekdays.items():
            if weekday_kor in date_str:
                days_to_add = (weekday_num - today.weekday()) % 7
                target_date = today + datetime.timedelta(days=days_to_add)
                print(f"디버깅: 이번주 요일 처리 - {date_str} -> {target_date}")
                return target_date.year, target_date.month, target_date.day
        
        print(f"디버깅: 상대적 날짜 파싱 실패 - 알 수 없는 표현: {date_str}")
        return None, None, None
        
    except Exception as e:
        print(f"디버깅: 상대적 날짜 파싱 오류 - {str(e)}")
        return None, None, None

def _parse_hour(hour_str: str) -> tuple:
    """시간 문자열을 파싱하여 24시간 형식으로 변환합니다."""
    print(f"디버깅: 시간 파싱 시작 - 입력: {hour_str}")
    try:
        # 24시간 형식인 경우
        if hour_str.isdigit():
            hour = int(hour_str)
            if 0 <= hour <= 23:
                print(f"디버깅: 24시간 형식 처리 - {hour}시")
                return hour, None
            return None, "죄송해요. 시간은 0-23 사이의 숫자로 입력해주세요."
        
        # 12시간 형식인 경우
        hour_str = hour_str.lower()
        if '오전' in hour_str or 'am' in hour_str:
            is_am = True
            hour_str = hour_str.replace('오전', '').replace('am', '').strip()
        elif '오후' in hour_str or 'pm' in hour_str:
            is_am = False
            hour_str = hour_str.replace('오후', '').replace('pm', '').strip()
        else:
            print(f"디버깅: 시간 형식 인식 실패 - {hour_str}")
            return None, "죄송해요. 시간은 '오전/오후' 또는 'AM/PM'을 포함하여 입력해주세요."
        
        # 숫자만 추출
        hour = int(''.join(filter(str.isdigit, hour_str)))
        if hour < 1 or hour > 12:
            return None, "죄송해요. 12시간 형식에서는 1-12 사이의 숫자로 입력해주세요."
        
        # 24시간 형식으로 변환
        if is_am:
            hour = 0 if hour == 12 else hour
        else:
            hour = hour if hour == 12 else hour + 12
        
        print(f"디버깅: 12시간 형식 처리 - {hour}시")
        return hour, None
        
    except ValueError as e:
        print(f"디버깅: 시간 파싱 오류 - {str(e)}")
        return None, "죄송해요. 시간 형식이 올바르지 않아요. 0-23 또는 오전/오후 1-12 형식으로 입력해주세요."

def validate_date_format(day: str, hour: str, month: str = None) -> tuple:
    """날짜와 시간 형식을 검증하고 datetime 객체를 생성합니다."""
    try:
        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month
        current_day = now.day
        
        # 시간 파싱
        parsed_hour, error = _parse_hour(hour)
        if error:
            return None, error
        input_hour = parsed_hour
        
        # YYYY-MM-DD 형식인 경우
        if '-' in day:
            try:
                date_parts = day.split('-')
                if len(date_parts) == 3:
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day = int(date_parts[2])
                    
                    # 날짜 유효성 검사
                    if month < 1 or month > 12:
                        return None, "죄송해요. 월은 1-12 사이의 숫자로 입력해주세요."
                    if day < 1 or day > 31:
                        return None, "죄송해요. 일은 1-31 사이의 숫자로 입력해주세요."
                    
                    start_dt = datetime.datetime(year, month, day, input_hour, 0)
                    end_dt = start_dt + datetime.timedelta(hours=1)
                    return start_dt, end_dt
            except ValueError as e:
                return None, "죄송해요. 날짜 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해주세요."
        
        # 상대적 날짜 처리
        year, month, day = _parse_relative_date(day)
        if year is not None:
            start_dt = datetime.datetime(year, month, day, input_hour, 0)
            end_dt = start_dt + datetime.timedelta(hours=1)
            return start_dt, end_dt
        
        # 기존 로직 (일과 시간만 입력된 경우)
        input_day = int(day)
        
        if month is None:
            input_month = current_month
        else:
            input_month = int(month)
        
        # 년도와 월 결정
        if month is None:
            if input_day < current_day:
                if current_month == 12:
                    year = current_year + 1
                    month = 1
                else:
                    year = current_year
                    month = current_month + 1
            else:
                year = current_year
                month = current_month
        else:
            if input_month < current_month:
                year = current_year + 1
            else:
                year = current_year
            month = input_month
        
        # 월별 최대 일수 검증
        if month in [4, 6, 9, 11]:
            max_day = 30
        elif month == 2:
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                max_day = 29
            else:
                max_day = 28
        else:
            max_day = 31
            
        if input_day > max_day:
            if month == 2:
                year_type = "윤년" if max_day == 29 else "평년"
                return None, f"죄송해요. {year}년 2월은 {year_type}으로 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."
            return None, f"죄송해요. {month}월은 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."
        
        start_dt = datetime.datetime.strptime(f"{year}-{month:02d}-{day:02d} {input_hour}:00", "%Y-%m-%d %H:%M")
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        return start_dt, end_dt
    except ValueError as e:
        return None, "죄송해요. 잘못된 날짜 또는 시간 형식이에요. 다시 입력해주세요." 