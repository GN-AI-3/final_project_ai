from datetime import datetime


class DateManager:
    """날짜 관련 유틸리티 클래스"""
    
    @staticmethod
    def get_formatted_date() -> tuple[str, datetime]:
        """현재 날짜를 형식화하여 반환합니다.
        
        Returns:
            tuple[str, datetime]: (형식화된 날짜 문자열, 현재 날짜 객체)
        """
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y년 %m월 %d일")
        return formatted_date, current_date 