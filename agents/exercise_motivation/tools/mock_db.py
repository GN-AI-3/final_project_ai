"""
테스트를 위한 모의 데이터베이스 도구
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

# 로깅 설정
logger = logging.getLogger(__name__)

class MockDBTools:
    """테스트용 모의 데이터베이스 도구"""
    
    # 모의 사용자 데이터
    user_data = {
        1: {  # 적극적인 사용자
            "pattern": "active",
            "total_records": 25,
            "attendance_rate": 0.83,
            "memo_rate": 0.9,
            "first_record_date": datetime.now() - timedelta(days=35),
            "preferred_time": "18:30",  # 저녁 시간에 운동
            "time_consistency": "high"
        },
        2: {  # 불규칙적 사용자
            "pattern": "irregular",
            "total_records": 12,
            "attendance_rate": 0.4,
            "memo_rate": 0.5,
            "first_record_date": datetime.now() - timedelta(days=30),
            "preferred_time": "12:00",  # 점심 시간에 운동
            "time_consistency": "medium"
        },
        3: {  # 비활성 사용자
            "pattern": "inactive",
            "total_records": 3,
            "attendance_rate": 0.1,
            "memo_rate": 0.33,
            "first_record_date": datetime.now() - timedelta(days=28),
            "preferred_time": "07:00",  # 아침에 운동
            "time_consistency": "low"
        },
        4: {  # 신규 사용자
            "pattern": "inactive",
            "total_records": 0,
            "attendance_rate": 0.0,
            "memo_rate": 0.0,
            "first_record_date": None,
            "preferred_time": "09:00",  # 기본값
            "time_consistency": "low"
        }
    }
    
    @staticmethod
    def connect_db() -> Tuple[str, str]:
        """
        모의 데이터베이스 연결
        
        Returns:
            Tuple[conn, cursor]: 연결 객체와 커서 (실제로는 더미 문자열)
        """
        logger.info("모의 DB 연결 성공")
        return "mock_conn", "mock_cursor"
    
    @staticmethod
    def get_user_exercise_records(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        특정 사용자의 최근 운동 기록을 모의로 생성합니다.
        
        Args:
            user_id: 사용자 ID
            days: 조회할 기간(일)
            
        Returns:
            List[Dict]: 모의 운동 기록 목록
        """
        # 사용자 ID가 없으면 빈 리스트 반환
        if user_id not in MockDBTools.user_data:
            logger.warning(f"사용자 {user_id}의 데이터가 없습니다.")
            return []
        
        user = MockDBTools.user_data[user_id]
        records = []
        
        # 첫 기록 날짜가 없으면 빈 리스트 반환
        if not user["first_record_date"]:
            return []
        
        # 선호 운동 시간을 시간과 분으로 변환
        preferred_hour = 9  # 기본값
        preferred_minute = 0
        
        if "preferred_time" in user:
            try:
                hour_str, minute_str = user["preferred_time"].split(":")
                preferred_hour = int(hour_str)
                preferred_minute = int(minute_str)
            except (ValueError, TypeError):
                pass
                
        # 시간 일관성에 따른 변동성 계산
        time_variance = 0
        if "time_consistency" in user:
            if user["time_consistency"] == "high":
                time_variance = 30  # 최대 30분 변동
            elif user["time_consistency"] == "medium":
                time_variance = 120  # 최대 2시간 변동
            else:
                time_variance = 240  # 최대 4시간 변동
        
        # 출석률에 따라 모의 기록 생성
        for i in range(days):
            # 출석률에 기반하여 운동했는지 여부 결정
            if random.random() <= user["attendance_rate"]:
                date = (datetime.now() - timedelta(days=i))
                
                # 시간 변동 추가 (일관성에 따라)
                minutes_variance = random.randint(-time_variance, time_variance)
                exercise_time = date.replace(
                    hour=preferred_hour, 
                    minute=preferred_minute
                ) + timedelta(minutes=minutes_variance)
                
                # 메모 작성 여부 결정
                has_memo = random.random() <= user["memo_rate"]
                memo = f"운동 {i+1}일차 기록입니다." if has_memo else ""
                
                record = {
                    "id": i + 1,
                    "member_id": user_id,
                    "exercise_date": date.strftime('%Y-%m-%d'),
                    "memo": memo,
                    "created_at": exercise_time.strftime('%Y-%m-%d %H:%M:%S')
                }
                records.append(record)
                
                # 총 기록 수에 도달하면 중단
                if len(records) >= user["total_records"]:
                    break
        
        logger.info(f"사용자 {user_id}의 모의 운동 기록 {len(records)}개 생성 완료")
        return records
    
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
                "attendance_rate": 0.0,
                "memo_rate": 0.0
            }
            
        # 기록 수
        total_records = len(records)
        
        # 출석률 계산 (최근 30일 기준)
        days = 30
        attendance_rate = min(1.0, total_records / days)
        
        # 메모 기록률 계산
        memo_rate = MockDBTools.calculate_memo_rate(records)
        
        # 운동 패턴 결정
        if attendance_rate >= 0.7:  # 70% 이상 출석
            pattern = "active"
        elif attendance_rate >= 0.3:  # 30% 이상 출석
            pattern = "irregular"
        else:
            pattern = "inactive"
            
        return {
            "pattern": pattern,
            "total_records": total_records,
            "attendance_rate": attendance_rate,
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
        
        # 사용자 ID로 사용자 정보 조회
        user_id = records[0].get("member_id") if records else None
        if user_id in MockDBTools.user_data:
            user = MockDBTools.user_data[user_id]
            
            # 모의 데이터 사용
            return {
                "preferred_time": user.get("preferred_time", "09:00"),
                "morning_ratio": 0.2 if "07:00" <= user.get("preferred_time", "09:00") < "12:00" else 0.1,
                "afternoon_ratio": 0.2 if "12:00" <= user.get("preferred_time", "09:00") < "18:00" else 0.1,
                "evening_ratio": 0.2 if "18:00" <= user.get("preferred_time", "09:00") < "23:00" else 0.1,
                "most_active_day": "월요일",
                "time_consistency": user.get("time_consistency", "low")
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
        most_active_day = days_count.most_common(1)[0][0] if days_count else "Monday"
        
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
        
        # 시간 일관성 (모의 데이터에서는 랜덤하게 설정)
        time_consistency_options = ["low", "medium", "high"]
        time_consistency = random.choice(time_consistency_options)
        
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
        동기부여 메시지 저장 모의 함수
        
        Args:
            user_id: 사용자 ID
            message: 동기부여 메시지
            
        Returns:
            bool: 저장 성공 여부
        """
        logger.info(f"사용자 {user_id}에 대한 동기부여 메시지 저장 완료 (모의)")
        return True