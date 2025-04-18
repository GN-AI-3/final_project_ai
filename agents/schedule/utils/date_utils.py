import re
from datetime import datetime, timedelta
from typing import Union, Tuple, Optional

def _parse_relative_date(date_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """상대적 날짜 표현을 파싱합니다. (예: 오늘, 내일, 다음주 수요일 등)
    
    Args:
        date_str: 파싱할 날짜 문자열
        
    Returns:
        Tuple[Optional[int], Optional[int], Optional[int]]: (년, 월, 일) 또는 (None, None, None)
    """
    now = datetime.now()
    today = now.date()
    
    weekdays = {
        '월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6
    }
    
    relative_dates = {
        '오늘': 0,
        '내일': 1,
        '모레': 2,
        '글피': 3,
        '다다음주': 14,
        '다음주': 7
    }

    try:
        date_str = date_str.strip().replace(" ", "")

        # 정확한 상대 표현 (오늘, 내일 등)
        if date_str in relative_dates:
            delta = relative_dates[date_str]
            target_date = today + timedelta(days=delta)
            return target_date.year, target_date.month, target_date.day

        # "다음주화요일", "다다음주목요일" 등의 표현
        for key in ["다다음주", "다음주"]:
            if key in date_str:
                for wk_kor, wk_num in weekdays.items():
                    if wk_kor in date_str:
                        base_delta = relative_dates[key]
                        days_to_add = base_delta + (wk_num - today.weekday()) % 7
                        target_date = today + timedelta(days=days_to_add)
                        return target_date.year, target_date.month, target_date.day

        # "이번주 X요일" 또는 단순 "X요일"
        for wk_kor, wk_num in weekdays.items():
            if wk_kor in date_str:
                days_to_add = (wk_num - today.weekday()) % 7
                if days_to_add == 0 and "오늘" not in date_str:
                    days_to_add = 7  # 오늘이 월요일인데 "월요일"이라고 하면 다음 주로 간주
                target_date = today + timedelta(days=days_to_add)
                return target_date.year, target_date.month, target_date.day

        return None, None, None

    except Exception as e:
        return None, None, None


def _parse_hour(hour_str: Union[str, int]) -> Tuple[Optional[int], Optional[str]]:
    """시간 문자열을 파싱하여 24시간 형식으로 변환합니다. (1시간 단위, 오전/오후, 한글 숫자 지원)
    
    Args:
        hour_str: 파싱할 시간 문자열
        
    Returns:
        Tuple[Optional[int], Optional[str]]: (시간, 에러 메시지)
    """
    korean_numbers = {
        "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6,
        "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
        "열한": 11, "열두": 12,
        "한시": 1, "두시": 2, "세시": 3, "네시": 4, "다섯시": 5, "여섯시": 6,
        "일곱시": 7, "여덟시": 8, "아홉시": 9, "열시": 10,
        "열한시": 11, "열두시": 12
    }

    try:
        original = str(hour_str)  # int → str 변환 추가
        hour_str = original.lower().strip().replace(" ", "")

        is_am = None
        if "오전" in hour_str or "am" in hour_str:
            is_am = True
            hour_str = hour_str.replace("오전", "").replace("am", "")
        elif "오후" in hour_str or "pm" in hour_str:
            is_am = False
            hour_str = hour_str.replace("오후", "").replace("pm", "")

        # 한글 숫자 처리
        for k_num, value in korean_numbers.items():
            if k_num in hour_str:
                hour = value
                break
        else:
            # 한글 아닌 경우 숫자 추출
            hour_str = re.sub(r"[^\d]", "", hour_str)
            if not hour_str:
                return None, f"죄송해요. '{original}'은(는) 올바른 시간 표현이 아니에요."
            hour = int(hour_str)

        # 12시간제 → 24시간제 변환
        if is_am is not None:
            if not (1 <= hour <= 12):
                return None, "12시간 형식에서는 1부터 12 사이로 입력해주세요."
            hour = 0 if hour == 12 and is_am else (hour if is_am else (hour + 12 if hour != 12 else 12))
        else:
            if not (0 <= hour <= 23):
                return None, "24시간 형식에서는 0부터 23 사이의 숫자를 입력해주세요."

        return hour, None

    except Exception as e:
        return None, "시간 형식이 잘못됐어요. 예: '오전 10시', '오후 다섯시', '15시'"


def validate_date_format(
    day: Union[str, int], 
    hour: Union[str, int], 
    month: Union[str, int, None] = None
) -> Tuple[Optional[datetime], Optional[str]]:
    """날짜와 시간 형식을 검증하고 datetime 객체를 생성합니다.
    
    Args:
        day: 일자 (문자열 또는 정수)
        hour: 시간 (문자열 또는 정수)
        month: 월 (문자열 또는 정수, 선택적)
        
    Returns:
        Tuple[Optional[datetime], Optional[str]]: (시작 datetime 객체, 에러 메시지)
    """
    try:
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_day = now.day
        
        # 시간 파싱
        parsed_hour, error = _parse_hour(str(hour))
        if error:
            return None, error
        input_hour = parsed_hour
        
        # YYYY-MM-DD 형식인 경우
        if isinstance(day, str) and '-' in day:
            try:
                date_parts = day.split('-')
                if len(date_parts) == 3:
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day = int(date_parts[2])
                    
                    if month < 1 or month > 12:
                        return None, "죄송해요. 월은 1-12 사이의 숫자로 입력해주세요."
                    if day < 1 or day > 31:
                        return None, "죄송해요. 일은 1-31 사이의 숫자로 입력해주세요."
                    
                    start_dt = datetime(year, month, day, input_hour, 0)
                    end_dt = start_dt + timedelta(hours=1)
                    return start_dt, end_dt
            except ValueError:
                return None, "죄송해요. 날짜 형식이 올바르지 않아요. YYYY-MM-DD 형식으로 입력해주세요."

        # X월 Y일 형식인 경우
        if isinstance(day, str) and '월' in day and '일' in day:
            try:
                month_part = day.split('월')[0]
                day_part = day.split('월')[1].split('일')[0]
                input_month = int(month_part)
                input_day = int(day_part)
                
                year = current_year + 1 if input_month < current_month else current_year
                
                if input_month in [4, 6, 9, 11]:
                    max_day = 30
                elif input_month == 2:
                    max_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
                else:
                    max_day = 31
                    
                if input_day > max_day:
                    if input_month == 2:
                        year_type = "윤년" if max_day == 29 else "평년"
                        return None, f"죄송해요. {year}년 2월은 {year_type}으로 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."
                    return None, f"죄송해요. {input_month}월은 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."

                start_dt = datetime(year, input_month, input_day, input_hour, 0)
                end_dt = start_dt + timedelta(hours=1)
                return start_dt, end_dt
            except ValueError:
                return None, "죄송해요. 날짜 형식이 올바르지 않아요. 'X월 Y일' 형식으로 입력해주세요."

        # YYYY년 MM월 DD일 형식인 경우
        if isinstance(day, str) and '년' in day and '월' in day and '일' in day:
            try:
                year_part = day.split('년')[0]
                month_part = day.split('년')[1].split('월')[0]
                day_part = day.split('월')[1].split('일')[0]
                
                year = int(year_part)
                input_month = int(month_part)
                input_day = int(day_part)
                
                if input_month < 1 or input_month > 12:
                    return None, "죄송해요. 월은 1-12 사이의 숫자로 입력해주세요."
                    
                if input_month in [4, 6, 9, 11]:
                    max_day = 30
                elif input_month == 2:
                    max_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
                else:
                    max_day = 31
                    
                if input_day > max_day:
                    if input_month == 2:
                        year_type = "윤년" if max_day == 29 else "평년"
                        return None, f"죄송해요. {year}년 2월은 {year_type}으로 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."
                    return None, f"죄송해요. {input_month}월은 {max_day}일까지 있어요. 1-{max_day} 사이의 날짜를 다시 입력해주세요."

                start_dt = datetime(year, input_month, input_day, input_hour, 0)
                end_dt = start_dt + timedelta(hours=1)
                return start_dt, end_dt
            except ValueError:
                return None, "죄송해요. 날짜 형식이 올바르지 않아요. 'YYYY년 MM월 DD일' 형식으로 입력해주세요."

        rel_year, rel_month, rel_day = _parse_relative_date(str(day))
        if rel_year is not None:
            start_dt = datetime(rel_year, rel_month, rel_day, input_hour, 0)
            end_dt = start_dt + timedelta(hours=1)
            return start_dt, end_dt

        # 일/시간만 입력된 경우 처리
        try:
            if day is None:
                raise ValueError("day 값이 None이에요.")
            input_day = int(day)
        except (ValueError, TypeError):
            return None, "죄송해요. 일자는 숫자로 입력해주세요."

        try:
            if month is not None:
                input_month = int(month)
            else:
                input_month = current_month
        except (ValueError, TypeError):
            return None, "죄송해요. 월은 숫자로 입력해주세요."

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
            year = current_year + 1 if input_month < current_month else current_year
            month = input_month

        if month in [4, 6, 9, 11]:
            max_day = 30
        elif month == 2:
            max_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
        else:
            max_day = 31
            
        if input_day > max_day:
            if month == 2:
                year_type = "윤년" if max_day == 29 else "평년"
                return None, f"죄송해요. {year}년 2월은 {year_type}으로 {max_day}일까지 있어요. 1-{max_day}일 사이의 날짜를 다시 입력해주세요."
            return None, f"죄송해요. {month}월은 {max_day}일까지 있어요. 1-{max_day}일 사이의 날짜를 다시 입력해주세요."

        start_dt = datetime(year, month, input_day, input_hour, 0)
        end_dt = start_dt + timedelta(hours=1)
        return start_dt, end_dt

    except Exception:
        error_msg = "죄송해요. 잘못된 날짜 또는 시간 형식이에요. 다시 입력해주세요."
        return None, error_msg
