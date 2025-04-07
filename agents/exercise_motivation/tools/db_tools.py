"""
사용자 운동 기록 및 메모 기록률 관련 DB 도구
"""
import os
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

# 로깅 설정
logger = logging.getLogger(__name__)

class ExerciseDBTools:
    """운동 기록 조회 및 메시지 저장 도구"""
    
    @staticmethod
    def connect_db() -> Tuple[Optional[psycopg2.extensions.connection], Optional[psycopg2.extensions.cursor]]:
        """
        데이터베이스 연결을 설정합니다.
        
        Returns:
            Tuple[conn, cursor]: 연결 객체와 커서
        """
        try:
            # 환경 변수에서 DB 연결 정보 가져오기
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5433")
            db_name = os.getenv("DB_NAME", "gym")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "set")
            
            # 연결 문자열 생성
            conn_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"
            
            # 데이터베이스 연결
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            
            logger.info(f"DB 연결 성공: {db_host}:{db_port}/{db_name}")
            return conn, cursor
            
        except Exception as e:
            logger.error(f"DB 연결 실패: {str(e)}")
            return None, None
    
    @staticmethod
    def get_user_exercise_records(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        특정 사용자의 최근 운동 기록을 조회합니다.
        
        Args:
            user_id: 사용자 ID
            days: 조회할 기간(일)
            
        Returns:
            List[Dict]: 운동 기록 목록
        """
        try:
            conn, cursor = ExerciseDBTools.connect_db()
            if not conn or not cursor:
                return []
            
            # 최근 N일 동안의 운동 기록 조회
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            query = """
            SELECT id, member_id, exercise_date, memo, created_at
            FROM public.exercise_record
            WHERE member_id = %s AND exercise_date >= %s
            ORDER BY exercise_date DESC
            """
            
            cursor.execute(query, (user_id, start_date))
            records = cursor.fetchall()
            
            # 결과 변환
            exercise_records = []
            for record in records:
                exercise_records.append({
                    "id": record[0],
                    "member_id": record[1],
                    "exercise_date": record[2].strftime('%Y-%m-%d') if record[2] else None,
                    "memo": record[3],
                    "created_at": record[4].strftime('%Y-%m-%d %H:%M:%S') if record[4] else None
                })
            
            # 연결 종료
            cursor.close()
            conn.close()
            
            logger.info(f"사용자 {user_id}의 운동 기록 {len(exercise_records)}개 조회 완료")
            return exercise_records
            
        except Exception as e:
            logger.error(f"운동 기록 조회 중 오류: {str(e)}")
            return []
    
    @staticmethod
    def calculate_memo_rate(records: List[Dict[str, Any]]) -> float:
        """
        메모 기록률을 계산합니다.
        
        Args:
            records: 운동 기록 목록
            
        Returns:
            float: 메모 기록률 (0.0 ~ 1.0)
        """
        if not records:
            return 0.0
            
        # 메모가 있는 기록 수 계산
        records_with_memo = [r for r in records if r.get("memo") and r["memo"].strip()]
        
        # 메모 기록률 계산
        memo_rate = len(records_with_memo) / len(records)
        
        logger.info(f"메모 기록률: {memo_rate:.2f} ({len(records_with_memo)}/{len(records)})")
        return memo_rate
    
    @staticmethod
    def get_exercise_weeks(records: List[Dict[str, Any]]) -> int:
        """
        운동 기록의 주차를 계산합니다 (첫 기록 기준).
        
        Args:
            records: 운동 기록 목록
            
        Returns:
            int: 주차 (1주차, 2주차, 3주차 등)
        """
        if not records:
            return 1
            
        # 첫 기록 날짜 찾기 (가장 오래된 날짜)
        first_record_date = None
        for record in records:
            date_str = record.get("exercise_date")
            if date_str:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                if first_record_date is None or date < first_record_date:
                    first_record_date = date
        
        if not first_record_date:
            return 1
            
        # 현재 날짜와의 차이를 주 단위로 계산
        today = datetime.now()
        days_diff = (today - first_record_date).days
        weeks = max(1, (days_diff // 7) + 1)  # 최소 1주차
        
        logger.info(f"첫 운동일 {first_record_date.strftime('%Y-%m-%d')} 기준 {weeks}주차")
        return weeks
    
    @staticmethod
    def get_exercise_pattern(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        운동 패턴을 분석합니다.
        
        Args:
            records: 운동 기록 목록
            
        Returns:
            Dict: 운동 패턴 분석 결과
        """
        if not records:
            return {
                "pattern": "inactive",
                "total_records": 0,
                "memo_rate": 0.0
            }
            
        # 기록 수
        total_records = len(records)
        
        # 메모 기록률 계산
        memo_rate = ExerciseDBTools.calculate_memo_rate(records)
        
        # 운동 패턴 결정 (메모 기록률 기준으로 변경)
        if memo_rate >= 0.7:  # 70% 이상 메모 작성
            pattern = "active"
        elif memo_rate >= 0.3:  # 30% 이상 메모 작성
            pattern = "irregular"
        else:
            pattern = "inactive"
            
        return {
            "pattern": pattern,
            "total_records": total_records,
            "memo_rate": memo_rate
        }
    
    @staticmethod
    def analyze_exercise_time(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        사용자의 운동 시간대를 분석합니다.
        
        Args:
            records: 운동 기록 목록
            
        Returns:
            Dict: 운동 시간대 분석 결과
        """
        if not records:
            return {
                "preferred_time": "09:00",  # 기본값
                "morning_ratio": 0,
                "afternoon_ratio": 0,
                "evening_ratio": 0,
                "most_active_day": "월요일",
                "time_consistency": "low"
            }
        
        # 시간대별 카운트
        time_slots = []
        days_count = Counter()
        
        for record in records:
            created_at = record.get("created_at")
            if created_at:
                try:
                    dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    time_slots.append(dt.hour)
                    days_count[dt.strftime('%A')] += 1  # 요일 카운트
                except (ValueError, TypeError):
                    continue
        
        if not time_slots:
            return {
                "preferred_time": "09:00",
                "morning_ratio": 0,
                "afternoon_ratio": 0,
                "evening_ratio": 0,
                "most_active_day": "월요일",
                "time_consistency": "low"
            }
        
        # 시간대별 분석
        morning_hours = sum(1 for h in time_slots if 5 <= h < 12)
        afternoon_hours = sum(1 for h in time_slots if 12 <= h < 18)
        evening_hours = sum(1 for h in time_slots if 18 <= h < 24 or 0 <= h < 5)
        
        total = len(time_slots)
        morning_ratio = morning_hours / total if total else 0
        afternoon_ratio = afternoon_hours / total if total else 0
        evening_ratio = evening_hours / total if total else 0
        
        # 가장 빈도가 높은 시간
        time_counter = Counter(time_slots)
        most_common_hour = time_counter.most_common(1)[0][0] if time_counter else 9
        preferred_time = f"{most_common_hour:02d}:00"
        
        # 가장 활동적인 요일
        most_active_day = days_count.most_common(1)[0][0] if days_count else "월요일"
        
        # 시간 일관성 계산 (가장 많은 시간대가 전체의 몇 %를 차지하는지)
        max_count = time_counter.most_common(1)[0][1] if time_counter else 0
        consistency_ratio = max_count / total if total else 0
        
        if consistency_ratio > 0.7:
            time_consistency = "high"
        elif consistency_ratio > 0.4:
            time_consistency = "medium"
        else:
            time_consistency = "low"
        
        # 한국어 요일 변환
        day_mapping = {
            "Monday": "월요일", 
            "Tuesday": "화요일", 
            "Wednesday": "수요일",
            "Thursday": "목요일", 
            "Friday": "금요일", 
            "Saturday": "토요일", 
            "Sunday": "일요일"
        }
        most_active_day_kr = day_mapping.get(most_active_day, most_active_day)
        
        return {
            "preferred_time": preferred_time,
            "morning_ratio": morning_ratio,
            "afternoon_ratio": afternoon_ratio,
            "evening_ratio": evening_ratio,
            "most_active_day": most_active_day_kr,
            "time_consistency": time_consistency
        }
    
    @staticmethod
    def save_motivation_message(user_id: int, message: str) -> bool:
        """
        동기부여 메시지를 저장합니다.
        
        Args:
            user_id: 사용자 ID
            message: 동기부여 메시지
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            conn, cursor = ExerciseDBTools.connect_db()
            if not conn or not cursor:
                return False
            
            # 현재 시간
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 메시지 저장
            query = """
            INSERT INTO public.motivation_messages (member_id, message, created_at)
            VALUES (%s, %s, %s)
            """
            
            cursor.execute(query, (user_id, message, now))
            conn.commit()
            
            # 연결 종료
            cursor.close()
            conn.close()
            
            logger.info(f"사용자 {user_id}의 동기부여 메시지 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"동기부여 메시지 저장 중 오류: {str(e)}")
            return False 