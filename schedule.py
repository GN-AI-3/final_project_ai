import os
from typing import Annotated, List, Optional
from typing_extensions import TypedDict
import datetime
import re
import random
import string

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.agents import tool
from langchain_community.utilities import SQLDatabase
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from langchain_teddynote import logging
from langchain_teddynote.graphs import visualize_graph
from langchain_teddynote.models import LLMs, get_model_name

# 환경 변수 로드
load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.db = SQLDatabase.from_uri(
            f"postgresql+psycopg2://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '1234')}@"
            f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'test')}"
        )

    @tool
    def get_schema(self):
        """데이터베이스 스키마 정보를 가져옵니다."""
        return self.db.get_table_info()
    
    @tool
    def run_query(self, query: str) -> str:
        """SQL 쿼리를 실행합니다."""
        try:
            result = self.db.run(query)
            return "데이터가 없습니다." if not result or result.strip() == "" else result
        except Exception as e:
            return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"

    def _execute_query(self, query: str) -> str:
        """내부적으로 SQL 쿼리를 실행합니다."""
        try:
            result = self.db.run(query)
            return "데이터가 없습니다." if not result or result.strip() == "" else result
        except Exception as e:
            return f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"

    def get_user_names(self) -> List[str]:
        """데이터베이스에서 사용자 이름 목록을 가져옵니다."""
        try:
            result = self._execute_query("SELECT name FROM users;")
            if result and result != "데이터가 없습니다.":
                result_list = eval(result)
                return [item[0] for item in result_list]
            return []
        except Exception as e:
            return []

    def get_user_schedule(self, name: str) -> str:
        """사용자의 예약 일정을 조회합니다."""
        query = f"""
        SELECT r.start_time, r.end_time, u.name as trainer_name, r.reservation_id,
               CONCAT(TO_CHAR(r.start_time, 'YYMMDD'), '_', r.random_code) as schedule_id
        FROM reservations r
        JOIN users u ON r.trainer_id = u.user_id
        WHERE r.user_id = (SELECT user_id FROM users WHERE name = '{name}')
        AND r.status = 'Confirmed'
        ORDER BY r.start_time;
        """
        return self._execute_query(query)

    def get_trainer_schedule(self, name: str) -> str:
        """트레이너의 예약 일정을 조회합니다."""
        query = f"""
        SELECT r.start_time, r.end_time, u.name as client_name, r.reservation_id,
               CONCAT(TO_CHAR(r.start_time, 'YYMMDD'), '_', r.random_code) as schedule_id
        FROM reservations r
        JOIN users u ON r.user_id = u.user_id
        WHERE r.trainer_id = (SELECT user_id FROM users WHERE name = '{name}' AND role = 'R')
        AND r.status = 'Confirmed'
        ORDER BY r.start_time;
        """
        return self._execute_query(query)

    def is_trainer(self, name: str) -> bool:
        """사용자가 트레이너인지 확인합니다."""
        query = f"""
        SELECT EXISTS (
            SELECT 1 FROM users 
            WHERE name = '{name}' AND role = 'R'
        );
        """
        result = self._execute_query(query)
        if result and result != "데이터가 없습니다.":
            result_list = eval(result)
            return result_list[0][0] if result_list else False
        return False

    def _generate_unique_random_code(self) -> str:
        """중복되지 않는 랜덤 코드를 생성합니다."""
        max_attempts = 10  # 최대 시도 횟수
        for _ in range(max_attempts):
            # 5자리 랜덤 코드 생성
            random_code = ''.join(random.choices(string.digits, k=5))
            
            # 중복 체크
            query = f"""
            SELECT EXISTS (
                SELECT 1 FROM reservations 
                WHERE random_code = '{random_code}'
            );
            """
            result = self._execute_query(query)
            
            if result and result != "데이터가 없습니다.":
                result_list = eval(result)
                if not result_list[0]:  # 중복되지 않는 경우
                    return random_code
        
        raise Exception("고유한 랜덤 코드를 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.")

    def create_reservation(self, user_name: str, trainer_name: str, start_time: str) -> str:
        """새로운 예약을 생성합니다."""
        # 중복되지 않는 랜덤 코드 생성
        random_code = self._generate_unique_random_code()
        
        query = f"""
        INSERT INTO reservations (user_id, trainer_id, start_time, end_time, status, created_at, random_code)
        SELECT 
            (SELECT user_id FROM users WHERE name = '{user_name}'),
            (SELECT user_id FROM users WHERE name = '{trainer_name}' AND role = 'R'),
            '{start_time}',
            '{start_time}'::timestamp + interval '1 hour',
            'Confirmed',
            CURRENT_TIMESTAMP,
            '{random_code}'
        RETURNING reservation_id;
        """
        return self._execute_query(query)

    def check_trainer_availability(self, trainer_name: str, start_time: str) -> bool:
        """트레이너의 해당 시간대 예약 가능 여부를 확인합니다."""
        query = f"""
        SELECT NOT EXISTS (
            SELECT 1 FROM reservations r
            JOIN users u ON r.trainer_id = u.user_id
            WHERE u.name = '{trainer_name}'
            AND r.status = 'Confirmed'
            AND (
                ('{start_time}'::timestamp BETWEEN r.start_time AND r.end_time)
                OR ('{start_time}'::timestamp + interval '1 hour' BETWEEN r.start_time AND r.end_time)
            )
        );
        """
        result = self._execute_query(query)
        if result and result != "데이터가 없습니다.":
            result_list = eval(result)
            return result_list[0][0] if result_list else False
        return False

    def cancel_reservation(self, reservation_id: int, reason: str) -> str:
        """예약을 취소합니다."""
        query = f"""
        UPDATE reservations 
        SET status = 'Canceled', reason = '{reason}'
        WHERE reservation_id = {reservation_id}
        RETURNING reservation_id;
        """
        return self._execute_query(query)

    def change_reservation(self, reservation_id: int, new_start_time: str, reason: str) -> str:
        """예약을 변경합니다."""
        # 1. 기존 예약 상태 변경
        update_query = f"""
        UPDATE reservations 
        SET status = 'Changed', reason = '{reason}'
        WHERE reservation_id = {reservation_id}
        RETURNING user_id, trainer_id;
        """
        result = self._execute_query(update_query)
        
        if result and result != "데이터가 없습니다.":
            result_list = eval(result)
            if result_list:
                user_id, trainer_id = result_list[0]
                # 중복되지 않는 랜덤 코드 생성
                random_code = self._generate_unique_random_code()
                # 2. 새로운 예약 생성
                insert_query = f"""
                INSERT INTO reservations (user_id, trainer_id, start_time, end_time, status, created_at, random_code)
                VALUES (
                    {user_id},
                    {trainer_id},
                    '{new_start_time}',
                    '{new_start_time}'::timestamp + interval '1 hour',
                    'Confirmed',
                    CURRENT_TIMESTAMP,
                    '{random_code}'
                )
                RETURNING reservation_id;
                """
                return self._execute_query(insert_query)
        
        return "데이터가 없습니다."

    def get_reservation_by_schedule_id(self, schedule_id: str) -> str:
        """스케줄 ID로 예약 정보를 조회합니다."""
        query = f"""
        SELECT r.start_time, r.end_time, u1.name as user_name, u2.name as trainer_name, r.reservation_id
        FROM reservations r
        JOIN users u1 ON r.user_id = u1.user_id
        JOIN users u2 ON r.trainer_id = u2.user_id
        WHERE CONCAT(TO_CHAR(r.start_time, 'YYMMDD'), '_', r.random_code) = '{schedule_id}'
        AND r.status = 'Confirmed';
        """
        return self._execute_query(query)

class ScheduleFormatter:
    @staticmethod
    def format_datetime(dt: datetime.datetime) -> str:
        """datetime 객체를 읽기 쉬운 형식으로 변환합니다."""
        return dt.strftime("%Y년 %m월 %d일 %H시 %M분")

    @staticmethod
    def parse_datetime(dt_str: str) -> datetime.datetime:
        """문자열을 datetime 객체로 변환합니다."""
        try:
            if isinstance(dt_str, str):
                if "datetime" in dt_str:
                    if "datetime.datetime" in dt_str:
                        return eval(dt_str)
                    dt_str = dt_str.replace("datetime.", "")
                    return eval(dt_str)
                try:
                    return datetime.datetime.fromisoformat(dt_str.replace(" ", "T"))
                except ValueError:
                    try:
                        return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        return dt_str
            return dt_str
        except Exception as e:
            return dt_str

    @staticmethod
    def format_schedule_result(result: str, is_trainer: bool = False) -> str:
        """예약 결과를 읽기 쉬운 형식으로 변환합니다."""
        try:
            schedule_list = eval(result)
            if not schedule_list:
                return "예약된 일정이 없습니다."
            
            formatted_schedules = []
            for start_time, end_time, name, _, schedule_id in schedule_list:
                parsed_start_time = ScheduleFormatter.parse_datetime(start_time)
                start = ScheduleFormatter.format_datetime(parsed_start_time)
                
                if is_trainer:
                    formatted_schedules.append(f"{start}에 {name} 회원님과 운동 예정이에요. (예약 번호: {schedule_id})")
                else:
                    formatted_schedules.append(f"{start}에 {name} 선생님과 운동 예정이에요. (예약 번호: {schedule_id})")
            
            return "\n".join(formatted_schedules)
        except Exception as e:
            return result

class NameExtractor:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def extract_name(self, text: str) -> Optional[str]:
        """사용자 입력에서 이름을 추출합니다."""
        user_names = self.db_manager.get_user_names()
        for name in user_names:
            if name in text:
                return name
        return None

class Chatbot:
    def __init__(self, db_manager: DatabaseManager, name_extractor: NameExtractor):
        self.db_manager = db_manager
        self.name_extractor = name_extractor
        self.model = ChatOpenAI(model=get_model_name(LLMs.GPT4), temperature=0)
        self.tools = [db_manager.get_schema, db_manager.run_query]
        self.model = self.model.bind_tools(self.tools)
        
        with open("prompt_kr.txt", "r", encoding="utf-8") as file:
            self.system_prompt = file.read().strip()
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        self.chain = self.prompt | self.model | StrOutputParser()
        
        # 예약 정보 수집을 위한 상태 관리
        self.reservation_state = {
            'user_name': None,
            'trainer_name': None,
            'year': None,
            'month': None,
            'day': None,
            'hour': None
        }

    def _get_available_trainers(self) -> List[str]:
        """사용 가능한 트레이너 목록을 가져옵니다."""
        query = "SELECT name FROM users WHERE role = 'R';"
        result = self.db_manager._execute_query(query)
        if result and result != "데이터가 없습니다.":
            result_list = eval(result)
            return [item[0] for item in result_list]
        return []

    def _validate_date(self, year: int, month: int, day: int) -> bool:
        """날짜가 유효한지 확인합니다."""
        try:
            datetime.datetime(year, month, day)
            return True
        except ValueError:
            return False

    def _validate_time(self, hour: int) -> bool:
        """시간이 유효한지 확인합니다."""
        return 0 <= hour <= 23

    def _extract_trainer_name(self, text: str) -> Optional[str]:
        """문장에서 트레이너 이름을 추출합니다."""
        trainers = self._get_available_trainers()
        for trainer in trainers:
            if trainer in text:
                return trainer
        return None

    def _get_next_reservation_question(self) -> str:
        """다음으로 필요한 예약 정보를 요청하는 메시지를 반환합니다."""
        if not self.reservation_state['user_name']:
            return "예약하시는 회원님의 이름을 알려주세요."
        if not self.reservation_state['trainer_name']:
            return "어떤 트레이너와 예약하시겠습니까?"
        if not self.reservation_state['year']:
            return "예약하실 연도나 날짜를 입력해 주세요. (예: 2025 또는 내일, 다음주 월요일)"
        if not self.reservation_state['month']:
            return "예약하실 월을 입력해 주세요. (1-12)"
        if not self.reservation_state['day']:
            return "예약하실 일을 입력해 주세요. (1-31)"
        if not self.reservation_state['hour']:
            return "예약하실 시간을 입력해 주세요. (0-23)"
        return None

    def _parse_relative_date(self, date_str: str) -> Optional[datetime.datetime]:
        """상대적인 날짜 표현을 datetime 객체로 변환합니다."""
        now = datetime.datetime.now()
        today = now.date()
        
        # 내일
        if "내일" in date_str:
            tomorrow = today + datetime.timedelta(days=1)
            return datetime.datetime.combine(tomorrow, now.time())
        
        # 모레
        if "모레" in date_str:
            day_after_tomorrow = today + datetime.timedelta(days=2)
            return datetime.datetime.combine(day_after_tomorrow, now.time())
        
        # 다음주
        if "다음주" in date_str:
            next_week = today + datetime.timedelta(days=7)
            return datetime.datetime.combine(next_week, now.time())
        
        # 요일 처리
        weekdays = {
            "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
            "금요일": 4, "토요일": 5, "일요일": 6
        }
        
        for weekday in weekdays:
            if weekday in date_str:
                current_weekday = today.weekday()
                target_weekday = weekdays[weekday]
                days_ahead = (target_weekday - current_weekday) % 7
                if days_ahead == 0 and "다음" in date_str:
                    days_ahead = 7
                target_date = today + datetime.timedelta(days=days_ahead)
                return datetime.datetime.combine(target_date, now.time())
        
        return None

    def _process_reservation_input(self, message: str) -> str:
        """사용자 입력을 처리하고 예약 정보를 업데이트합니다."""
        # 1. 사용자 이름 추출
        if not self.reservation_state['user_name']:
            self.reservation_state['user_name'] = self.name_extractor.extract_name(message)
            if not self.reservation_state['user_name']:
                return "입력하신 이름을 찾을 수 없습니다. 다시 시도해 주세요."
        
        # 2. 트레이너 이름 추출
        if not self.reservation_state['trainer_name']:
            trainer_name = self._extract_trainer_name(message)
            if trainer_name:
                if not self.db_manager.is_trainer(trainer_name):
                    return "해당 트레이너를 찾을 수 없습니다. 다시 시도해 주세요."
                self.reservation_state['trainer_name'] = trainer_name
        
        # 3. 날짜와 시간 추출
        relative_date = self._parse_relative_date(message)
        if relative_date:
            self.reservation_state['year'] = relative_date.year
            self.reservation_state['month'] = relative_date.month
            self.reservation_state['day'] = relative_date.day
        
        # 시간 추출
        time_match = re.search(r'(\d{1,2})시', message)
        if time_match:
            try:
                hour = int(time_match.group(1))
                if self._validate_time(hour):
                    self.reservation_state['hour'] = hour
            except ValueError:
                pass
        
        # 모든 정보가 수집되었는지 확인
        if all(self.reservation_state.values()):
            # 예약 생성
            start_time = f"{self.reservation_state['year']}-{self.reservation_state['month']:02d}-{self.reservation_state['day']:02d} {self.reservation_state['hour']:02d}:00:00"
            
            if not self.db_manager.check_trainer_availability(self.reservation_state['trainer_name'], start_time):
                return f"죄송합니다. {self.reservation_state['trainer_name']} 선생님의 해당 시간대는 이미 예약되어 있습니다."
            
            result = self.db_manager.create_reservation(
                self.reservation_state['user_name'],
                self.reservation_state['trainer_name'],
                start_time
            )
            
            if result and result != "데이터가 없습니다.":
                response = f"예약이 완료되었습니다. {self.reservation_state['trainer_name']} 선생님과 {self.reservation_state['year']}년 {self.reservation_state['month']}월 {self.reservation_state['day']}일 {self.reservation_state['hour']}시에 운동 예정입니다."
            else:
                response = "죄송합니다. 예약 생성 중 오류가 발생했습니다."
            
            # 예약 상태 초기화
            self.reservation_state = {
                'user_name': None,
                'trainer_name': None,
                'year': None,
                'month': None,
                'day': None,
                'hour': None
            }
            return response
        
        # 누락된 정보가 있는 경우 다음 질문 반환
        return self._get_next_reservation_question()

    def _process_schedule_change(self, message: str) -> str:
        """예약 변경/취소 요청을 처리합니다."""
        # 예약 번호 추출 (YYMMDD_XXXXX 형식)
        schedule_id_match = re.search(r'예약 번호: ([0-9]{6}_[0-9]{5})', message)
        
        # 예약 번호가 없는 경우, 사용자 이름 추출
        if not schedule_id_match:
            user_name = self.name_extractor.extract_name(message)
            if not user_name:
                return "예약 번호를 입력하거나, 예약을 변경/취소하려는 회원님의 이름을 입력해 주세요."
            
            # 사용자의 예약 목록 조회
            result = self.db_manager.get_user_schedule(user_name)
            if result == "데이터가 없습니다.":
                return f"{user_name}님의 예약된 일정이 없습니다."
            
            schedule_list = eval(result)
            if not schedule_list:
                return f"{user_name}님의 예약된 일정이 없습니다."
            
            # 예약 목록 표시
            formatted_schedules = []
            for i, (start_time, end_time, name, _, schedule_id) in enumerate(schedule_list, 1):
                parsed_start_time = ScheduleFormatter.parse_datetime(start_time)
                start = ScheduleFormatter.format_datetime(parsed_start_time)
                formatted_schedules.append(f"{i}. {start}에 {name} 선생님과 운동 예정이에요. (예약 번호: {schedule_id})")
            
            return f"{user_name}님의 예약 목록입니다:\n" + "\n".join(formatted_schedules) + "\n\n변경하거나 취소하려는 예약의 번호를 입력해 주세요."
        
        schedule_id = schedule_id_match.group(1)
        
        # 예약 존재 여부 확인
        result = self.db_manager.get_reservation_by_schedule_id(schedule_id)
        if result == "데이터가 없습니다.":
            return "해당 예약을 찾을 수 없습니다."
        
        result_list = eval(result)
        if not result_list:
            return "해당 예약을 찾을 수 없습니다."
        
        reservation_id = result_list[0][4]  # reservation_id는 5번째 요소
        
        # 취소 요청 처리
        if "취소" in message:
            reason_match = re.search(r'취소.*?이유[는은]?\s*([^.]+)', message)
            if not reason_match:
                return "취소 사유를 입력해 주세요. (예: 예약 번호: 240315_12345 예약 취소 이유는 개인 사정)"
            
            reason = reason_match.group(1).strip()
            result = self.db_manager.cancel_reservation(reservation_id, reason)
            
            if result and result != "데이터가 없습니다.":
                return "예약이 취소되었습니다."
            return "예약 취소 중 오류가 발생했습니다."
        
        # 변경 요청 처리
        if "변경" in message:
            reason_match = re.search(r'변경.*?이유[는은]?\s*([^.]+)', message)
            if not reason_match:
                return "변경 사유를 입력해 주세요. (예: 예약 번호: 240315_12345 예약 변경 이유는 개인 사정)"
            
            reason = reason_match.group(1).strip()
            
            # 새로운 시간 추출
            relative_date = self._parse_relative_date(message)
            if not relative_date:
                return "변경할 날짜를 입력해 주세요. (예: 예약 번호: 240315_12345 예약 변경 이유는 개인 사정, 다음주 월요일로)"
            
            time_match = re.search(r'(\d{1,2})시', message)
            if not time_match:
                return "변경할 시간을 입력해 주세요. (예: 예약 번호: 240315_12345 예약 변경 이유는 개인 사정, 다음주 월요일 9시로)"
            
            try:
                hour = int(time_match.group(1))
                if not self._validate_time(hour):
                    return "올바른 시간을 입력해 주세요. (0-23)"
                
                new_start_time = f"{relative_date.year}-{relative_date.month:02d}-{relative_date.day:02d} {hour:02d}:00:00"
                
                # 트레이너의 새로운 시간대 예약 가능 여부 확인
                _, _, _, trainer_name = result_list[0]
                if not self.db_manager.check_trainer_availability(trainer_name, new_start_time):
                    return f"죄송합니다. {trainer_name} 선생님의 해당 시간대는 이미 예약되어 있습니다."
                
                # 예약 변경 실행
                result = self.db_manager.change_reservation(reservation_id, new_start_time, reason)
                if result and result != "데이터가 없습니다.":
                    return f"예약이 변경되었습니다. {relative_date.year}년 {relative_date.month}월 {relative_date.day}일 {hour}시로 변경되었습니다."
                return "예약 변경 중 오류가 발생했습니다."
            
            except ValueError:
                return "올바른 시간을 입력해 주세요."
        
        return "예약 변경 또는 취소를 명확히 입력해 주세요."

    def process_message(self, messages: List[BaseMessage]) -> str:
        """사용자 메시지를 처리하고 응답을 생성합니다."""
        try:
            last_message = messages[-1].content
            
            # 예약 관련 키워드가 있는 경우
            if "예약" in last_message.lower():
                if "취소" in last_message.lower() or "변경" in last_message.lower():
                    return self._process_schedule_change(last_message)
                return self._process_reservation_input(last_message)
            
            # 기존의 일정 조회 로직
            response = self.chain.invoke({"messages": messages})
            extracted_name = self.name_extractor.extract_name(last_message)
            
            if extracted_name:
                is_trainer = self.db_manager.is_trainer(extracted_name)
                if is_trainer:
                    result = self.db_manager.get_trainer_schedule(extracted_name)
                    if result and result != "데이터가 없습니다.":
                        formatted_result = ScheduleFormatter.format_schedule_result(result, is_trainer=True)
                        response = f"{extracted_name} 선생님의 예약 일정입니다:\n{formatted_result}"
                    else:
                        response = f"{extracted_name} 선생님의 예약된 일정이 없습니다."
                else:
                    result = self.db_manager.get_user_schedule(extracted_name)
                    if result and result != "데이터가 없습니다.":
                        formatted_result = ScheduleFormatter.format_schedule_result(result)
                        response = f"{extracted_name}님의 예약 일정입니다:\n{formatted_result}"
                    else:
                        response = f"{extracted_name}님의 예약된 일정이 없습니다."
            elif not response or response.strip() == "":
                response = "죄송합니다. 입력하신 이름을 찾을 수 없습니다. 다시 시도해 주세요."
            
            return response
        except Exception as e:
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}"

# State 정의
class State(TypedDict):
    messages: Annotated[list, add_messages]

def ai_assistant_node(state: State, chatbot: Chatbot):
    """AI 도우미 노드 함수"""
    messages = state["messages"]
    ai_response = chatbot.process_message(messages)
    print(f"\033[1;32m일정 도우미\033[0m: {ai_response}")
    return {"messages": messages + [AIMessage(content=ai_response)]}

def user_node(state: State):
    """사용자 입력 노드 함수"""
    print("\n")
    user_input = input(f"\033[1;36m사용자\033[0m: ")
    if user_input.strip().upper() == "종료":
        return {"messages": state["messages"] + [HumanMessage(content="종료")]}
    return {"messages": state["messages"] + [HumanMessage(content=user_input)]}

def should_continue(state: State):
    """대화 종료 여부를 판단하는 함수"""
    return "end" if state["messages"][-1].content == "종료" else "continue"

def build_graph(chatbot: Chatbot):
    """대화 그래프를 구축하는 함수"""
    graph_builder = StateGraph(State)

    # 노드 추가
    graph_builder.add_node("사용자", user_node)
    graph_builder.add_node("일정 도우미", lambda state: ai_assistant_node(state, chatbot))

    # 엣지 정의
    graph_builder.add_edge("일정 도우미", "사용자")

    # 조건부 엣지 정의
    graph_builder.add_conditional_edges(
        "사용자",
        should_continue,
        {
            "end": END,
            "continue": "일정 도우미",
        },
    )

    graph_builder.set_entry_point("일정 도우미")
    return graph_builder.compile()

def run_graph_simulation():
    """그래프 시뮬레이션을 실행하는 함수"""
    # 컴포넌트 초기화
    db_manager = DatabaseManager()
    name_extractor = NameExtractor(db_manager)
    chatbot = Chatbot(db_manager, name_extractor)

    # 그래프 구축 및 실행
    simulation = build_graph(chatbot)
    visualize_graph(simulation)

    config = RunnableConfig(recursion_limit=100, configurable={"thread_id": "1"})
    inputs = {"messages": [HumanMessage(content="안녕하세요?")]}

    # 그래프 스트리밍 실행
    for chunk in simulation.stream(inputs, config):
        pass

# LangSmith 로그 설정
PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "default_project")
if PROJECT_NAME:
    logging.langsmith(PROJECT_NAME)

# 실행
if __name__ == "__main__":
    run_graph_simulation()
