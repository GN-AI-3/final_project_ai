import os
import random
import string
from typing import List, Optional
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseManager:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def _execute_query(self, query: str) -> str:
        """SQL 쿼리를 실행하고 결과를 반환합니다."""
        try:
            self.cur.execute(query)
            self.conn.commit()
            result = self.cur.fetchall()
            if not result:
                return "데이터가 없습니다."
            return str(result)
        except Exception as e:
            self.conn.rollback()
            return f"오류가 발생했습니다: {str(e)}"

    def _generate_unique_random_code(self) -> str:
        """중복되지 않는 랜덤 코드를 생성합니다."""
        max_attempts = 10
        for _ in range(max_attempts):
            random_code = ''.join(random.choices(string.digits, k=5))
            query = f"""
            SELECT EXISTS (
                SELECT 1 FROM reservations 
                WHERE random_code = '{random_code}'
            );
            """
            result = self._execute_query(query)
            
            if result and result != "데이터가 없습니다.":
                result_list = eval(result)
                if not result_list[0]:
                    return random_code
        
        raise Exception("고유한 랜덤 코드를 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.")

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

    def create_reservation(self, user_name: str, trainer_name: str, start_time: str) -> str:
        """새로운 예약을 생성합니다."""
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

    def change_reservation(self, reservation_id: int, new_start_time: str, reason: str) -> str:
        """예약을 변경합니다."""
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
                random_code = self._generate_unique_random_code()
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

    def cancel_reservation(self, reservation_id: int, reason: str) -> str:
        """예약을 취소합니다."""
        query = f"""
        UPDATE reservations 
        SET status = 'Canceled', reason = '{reason}'
        WHERE reservation_id = {reservation_id}
        RETURNING reservation_id;
        """
        return self._execute_query(query)

    def check_trainer_availability(self, trainer_name: str, start_time: str) -> bool:
        """트레이너의 특정 시간대 예약 가능 여부를 확인합니다."""
        query = f"""
        SELECT EXISTS (
            SELECT 1 FROM reservations r
            JOIN users u ON r.trainer_id = u.user_id
            WHERE u.name = '{trainer_name}'
            AND r.start_time = '{start_time}'
            AND r.status = 'Confirmed'
        );
        """
        result = self._execute_query(query)
        if result and result != "데이터가 없습니다.":
            result_list = eval(result)
            return not result_list[0]
        return True

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
            return result_list[0]
        return False

    def __del__(self):
        """데이터베이스 연결을 종료합니다."""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close() 