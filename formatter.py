import datetime
import re
from typing import Optional

class ScheduleFormatter:
    @staticmethod
    def parse_datetime(dt_str: str) -> datetime.datetime:
        """문자열을 datetime 객체로 변환합니다."""
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")

    @staticmethod
    def format_datetime(dt: datetime.datetime) -> str:
        """datetime 객체를 읽기 쉬운 형식으로 변환합니다."""
        return f"{dt.year}년 {dt.month}월 {dt.day}일 {dt.hour}시"

    @staticmethod
    def format_schedule_result(result: str, is_trainer: bool = False) -> str:
        """예약 결과를 읽기 쉬운 형식으로 변환합니다."""
        try:
            schedule_list = eval(result)
            if not schedule_list:
                return "예약된 일정이 없습니다."
            
            formatted_schedules = []
            for i, (start_time, end_time, name, _, schedule_id) in enumerate(schedule_list, 1):
                parsed_start_time = ScheduleFormatter.parse_datetime(start_time)
                start = ScheduleFormatter.format_datetime(parsed_start_time)
                
                if is_trainer:
                    formatted_schedules.append(f"{i}. {start}에 {name} 회원님과 운동 예정이에요. (예약 번호: {schedule_id})")
                else:
                    formatted_schedules.append(f"{i}. {start}에 {name} 선생님과 운동 예정이에요. (예약 번호: {schedule_id})")
            
            return "\n".join(formatted_schedules)
        except Exception as e:
            return result

    @staticmethod
    def parse_relative_date(message: str) -> Optional[datetime.datetime]:
        """상대적 날짜 표현을 datetime 객체로 변환합니다."""
        today = datetime.datetime.now()
        
        if "내일" in message:
            return today + datetime.timedelta(days=1)
        elif "모레" in message:
            return today + datetime.timedelta(days=2)
        elif "다음주" in message:
            # 다음주 월요일 찾기
            next_week = today + datetime.timedelta(days=7)
            days_ahead = 0 - next_week.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_monday = next_week + datetime.timedelta(days=days_ahead)
            
            # 요일 매칭
            weekday_map = {
                "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
                "금요일": 4, "토요일": 5, "일요일": 6
            }
            
            for weekday in weekday_map:
                if weekday in message:
                    days_ahead = weekday_map[weekday] - next_monday.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    return next_monday + datetime.timedelta(days=days_ahead)
            
            return next_monday
        
        # 연도 추출 시도
        year_match = re.search(r'(\d{4})년', message)
        if year_match:
            year = int(year_match.group(1))
            if year < today.year:
                return None
            
            # 월 추출
            month_match = re.search(r'(\d{1,2})월', message)
            if month_match:
                month = int(month_match.group(1))
                if not 1 <= month <= 12:
                    return None
                
                # 일 추출
                day_match = re.search(r'(\d{1,2})일', message)
                if day_match:
                    day = int(day_match.group(1))
                    try:
                        return datetime.datetime(year, month, day)
                    except ValueError:
                        return None
        
        return None

    @staticmethod
    def validate_time(hour: int) -> bool:
        """시간이 유효한지 확인합니다."""
        return 0 <= hour <= 23 