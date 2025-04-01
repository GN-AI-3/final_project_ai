from typing import Dict, Optional
from database import DatabaseManager
from formatter import ScheduleFormatter
from name_extractor import NameExtractor

class Chatbot:
    def __init__(self):
        self.db = DatabaseManager()
        self.reservation_states: Dict[str, Dict] = {}
        self.formatter = ScheduleFormatter()
        self.name_extractor = NameExtractor()

    def _get_available_trainers(self) -> list:
        """사용 가능한 트레이너 목록을 가져옵니다."""
        query = "SELECT name FROM users WHERE role = 'R'"
        result = self.db.execute_query(query)
        return [row[0] for row in result]

    def _validate_date(self, year: int, month: int, day: int) -> bool:
        """날짜가 유효한지 확인합니다."""
        try:
            datetime.datetime(year, month, day)
            return True
        except ValueError:
            return False

    def _get_next_reservation_question(self, state: Dict) -> str:
        """다음 예약 질문을 반환합니다."""
        if not state.get('user_name'):
            return "예약하시는 분의 이름을 알려주세요."
        elif not state.get('trainer_name'):
            return "어떤 트레이너와 예약하시겠습니까?"
        elif not state.get('year'):
            return "예약하실 연도를 알려주세요. (예: 2024년)"
        elif not state.get('month'):
            return "예약하실 월을 알려주세요. (예: 3월)"
        elif not state.get('day'):
            return "예약하실 일을 알려주세요. (예: 15일)"
        elif not state.get('hour'):
            return "예약하실 시간을 알려주세요. (0-23시)"
        return ""

    def _process_reservation_input(self, user_name: str, message: str) -> str:
        """예약 입력을 처리합니다."""
        if user_name not in self.reservation_states:
            self.reservation_states[user_name] = {
                'user_name': None,
                'trainer_name': None,
                'year': None,
                'month': None,
                'day': None,
                'hour': None
            }
        
        state = self.reservation_states[user_name]
        
        # 모든 정보가 한 번에 제공된 경우 처리
        if not state['user_name']:
            state['user_name'] = user_name
        
        if not state['trainer_name']:
            trainer_name = self.name_extractor.extract_name(message)
            if trainer_name:
                if trainer_name in self._get_available_trainers():
                    state['trainer_name'] = trainer_name
                else:
                    return "해당 트레이너를 찾을 수 없습니다. 다시 시도해주세요."
        
        if not state['year']:
            parsed_date = self.formatter.parse_relative_date(message)
            if parsed_date:
                state['year'] = parsed_date.year
                state['month'] = parsed_date.month
                state['day'] = parsed_date.day
            else:
                year_match = re.search(r'(\d{4})년', message)
                if year_match:
                    state['year'] = int(year_match.group(1))
        
        if not state['month'] and not parsed_date:
            month_match = re.search(r'(\d{1,2})월', message)
            if month_match:
                state['month'] = int(month_match.group(1))
        
        if not state['day'] and not parsed_date:
            day_match = re.search(r'(\d{1,2})일', message)
            if day_match:
                state['day'] = int(day_match.group(1))
        
        if not state['hour']:
            hour_match = re.search(r'(\d{1,2})시', message)
            if hour_match:
                hour = int(hour_match.group(1))
                if self.formatter.validate_time(hour):
                    state['hour'] = hour
        
        # 모든 정보가 수집되었는지 확인
        if all(state.values()):
            # 날짜 유효성 검사
            if not self._validate_date(state['year'], state['month'], state['day']):
                return "잘못된 날짜입니다. 다시 시도해주세요."
            
            # 트레이너 가용성 확인
            if not self.db.check_trainer_availability(
                state['trainer_name'],
                state['year'],
                state['month'],
                state['day'],
                state['hour']
            ):
                return "해당 시간에 이미 예약이 있습니다. 다른 시간을 선택해주세요."
            
            # 예약 생성
            if self.db.create_reservation(
                state['user_name'],
                state['trainer_name'],
                state['year'],
                state['month'],
                state['day'],
                state['hour']
            ):
                # 상태 초기화
                self.reservation_states[user_name] = {
                    'user_name': None,
                    'trainer_name': None,
                    'year': None,
                    'month': None,
                    'day': None,
                    'hour': None
                }
                return f"예약이 완료되었습니다! {state['trainer_name']} 선생님과 {state['year']}년 {state['month']}월 {state['day']}일 {state['hour']}시에 뵙겠습니다."
            else:
                return "예약 생성 중 오류가 발생했습니다. 다시 시도해주세요."
        
        # 다음 질문 반환
        return self._get_next_reservation_question(state)

    def process_message(self, message: str, user_name: str) -> str:
        """사용자 메시지를 처리합니다."""
        # 예약 관련 키워드 확인
        if "예약" in message:
            return self._process_reservation_input(user_name, message)
        
        # 일정 조회
        if "일정" in message or "스케줄" in message:
            # 트레이너 이름이 언급되었는지 확인
            trainer_name = self.name_extractor.extract_name(message)
            if trainer_name:
                if self.db.is_trainer(trainer_name):
                    result = self.db.get_trainer_schedule(trainer_name)
                    return self.formatter.format_schedule_result(result, True)
                else:
                    return "해당 트레이너를 찾을 수 없습니다."
            else:
                result = self.db.get_user_schedule(user_name)
                return self.formatter.format_schedule_result(result)
        
        return "죄송합니다. 이해하지 못했습니다. 예약이나 일정 조회를 원하시면 말씀해주세요." 