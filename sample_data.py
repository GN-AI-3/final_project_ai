"""
헬스장 회원 관리 시스템 샘플 데이터 생성 스크립트
"""
import logging
from db_models import MemberModel, AttendanceModel, ScheduleModel
from db_schema import create_database_schema
from datetime import date, timedelta
import random

logger = logging.getLogger(__name__)

# 샘플 회원 데이터
SAMPLE_MEMBERS = [
    {
        "name": "김영희",
        "email": "user1@example.com",
        "goal": "체중 감량",
        "role": "member",
        "fcm_token": "fcm_token_1",
        "schedule": [0, 2, 4]  # 월, 수, 금
    },
    {
        "name": "이철수",
        "email": "user2@example.com",
        "goal": "체형 관리",
        "role": "member",
        "fcm_token": "fcm_token_2",
        "schedule": [1, 3]  # 화, 목
    },
    {
        "name": "박지민",
        "email": "user3@example.com",
        "goal": "신체 능력 강화",
        "role": "member",
        "fcm_token": "fcm_token_3",
        "schedule": [0, 1, 2, 3, 4]  # 월~금
    },
    {
        "name": "최민수",
        "email": "user4@example.com",
        "goal": "건강 유지",
        "role": "member",
        "fcm_token": "fcm_token_4",
        "schedule": [0, 1, 3, 4]  # 월, 화, 목, 금
    },
    {
        "name": "정수연",
        "email": "user5@example.com",
        "goal": "정신적 건강 관리",
        "role": "member",
        "fcm_token": "fcm_token_5",
        "schedule": [1, 3, 5]  # 화, 목, 토
    },
    {
        "name": "강준호",
        "email": "user6@example.com",
        "goal": "취미",
        "role": "member",
        "fcm_token": "fcm_token_6",
        "schedule": [2, 4, 6]  # 수, 금, 일
    },
    {
        "name": "한지훈",
        "email": "trainer1@example.com",
        "goal": "신체 능력 강화",
        "role": "trainer",
        "fcm_token": "fcm_token_7",
        "schedule": [0, 1, 2, 3, 4]  # 월~금
    }
]

def create_sample_members():
    """샘플 회원 데이터 생성"""
    logger.info("샘플 회원 데이터 생성 중...")
    
    member_ids = []
    for member_data in SAMPLE_MEMBERS:
        # 회원 정보에서 스케줄 정보 분리
        schedule = member_data.pop("schedule", [])
        
        member_id = MemberModel.create_member(
            name=member_data["name"],
            email=member_data["email"],
            goal=member_data["goal"],
            role=member_data["role"],
            fcm_token=member_data["fcm_token"]
        )
        
        if member_id:
            member_ids.append(member_id)
            logger.info(f"회원 생성 완료: {member_data['name']} (ID: {member_id})")
            
            # 회원 스케줄 설정
            if schedule:
                ScheduleModel.set_member_schedule(member_id, schedule)
                weekday_names = [ScheduleModel.get_weekday_name(d) for d in schedule]
                logger.info(f"회원 {member_data['name']}의 스케줄 설정: {', '.join(weekday_names)}")
        else:
            logger.error(f"회원 생성 실패: {member_data['name']}")
    
    logger.info(f"총 {len(member_ids)}명의 샘플 회원 데이터 생성 완료")
    return member_ids

def create_sample_attendance(member_ids):
    """샘플 출석 데이터 생성"""
    if not member_ids:
        logger.warning("생성된 회원이 없어 출석 데이터를 생성할 수 없습니다.")
        return
    
    logger.info("샘플 출석 데이터 생성 중...")
    
    # 지난 90일간의 출석 데이터 생성
    today = date.today()
    start_date = today - timedelta(days=90)
    
    attendance_counts = 0
    
    for member_id in member_ids:
        # 회원 정보 조회
        member = MemberModel.get_member_by_id(member_id)
        if not member:
            continue
        
        # 회원 스케줄 조회
        schedule = ScheduleModel.get_member_schedule(member_id)
        
        # 날짜별 출석 데이터 생성
        current_date = start_date
        while current_date <= today:
            # 요일 확인 (0: 월요일, 1: 화요일, ...)
            weekday = current_date.weekday()
            
            # 스케줄이 있는 경우 해당 요일만 출석 생성, 없는 경우 평일만 출석 생성
            is_scheduled_day = (schedule and weekday in schedule) or (not schedule and weekday < 5)
            
            if is_scheduled_day:
                # 회원별 출석률 설정 (역할과 이메일에 따라 다르게 설정)
                if member["role"] == "trainer":
                    attendance_probability = 0.9  # 트레이너는 90% 출석률
                else:
                    # 기존 SAMPLE_USERS의 출석률 패턴을 유지
                    if "user1" in member["email"] or "user4" in member["email"]:
                        attendance_probability = 0.85  # 85% 출석률
                    elif "user2" in member["email"] or "user5" in member["email"]:
                        attendance_probability = 0.55  # 55% 출석률
                    else:
                        attendance_probability = 0.25  # 25% 출석률
                
                # 확률에 따라 출석 여부 결정
                if random.random() < attendance_probability:
                    # 가끔 지각 상태 추가
                    status = "출석" if random.random() < 0.9 else "지각"
                    
                    attendance_id = AttendanceModel.record_attendance(
                        member_id=member_id,
                        attendance_date=current_date,
                        status=status
                    )
                    
                    if attendance_id:
                        attendance_counts += 1
                else:
                    # 결석 처리 - 실제 개발 시 자동 결석 처리 함수로 대체
                    AttendanceModel.record_attendance(
                        member_id=member_id,
                        attendance_date=current_date,
                        status="결석"
                    )
            
            current_date += timedelta(days=1)
    
    logger.info(f"총 {attendance_counts}개의 샘플 출석 데이터 생성 완료")

def main():
    """샘플 데이터 생성 메인 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("데이터베이스 스키마 생성 시작...")
    if create_database_schema():
        logger.info("데이터베이스 스키마 생성 완료")
        
        # 회원 데이터 생성
        member_ids = create_sample_members()
        
        # 출석 데이터 생성
        create_sample_attendance(member_ids)
        
        logger.info("모든 샘플 데이터 생성 완료")
    else:
        logger.error("데이터베이스 스키마 생성 실패")

if __name__ == "__main__":
    main() 