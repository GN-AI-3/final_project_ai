#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
헬스장 회원 스케줄 관리 유틸리티 스크립트
"""
import os
import sys
import logging
import argparse
from dotenv import load_dotenv
from db_models import MemberModel, ScheduleModel
from datetime import date, datetime, timedelta

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("schedule_management.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def list_members():
    """모든 회원 목록 출력"""
    members = MemberModel.get_all_members()
    if not members:
        print("등록된 회원이 없습니다.")
        return
    
    print(f"\n총 {len(members)}명의 회원이 있습니다.")
    print("-" * 80)
    print(f"{'ID':^5} | {'이름':^10} | {'이메일':^25} | {'역할':^8} | {'목표':^15}")
    print("-" * 80)
    
    for member in members:
        print(f"{member['id']:^5} | {member['name']:^10} | {member['email']:^25} | {member['role']:^8} | {member['goal']:^15}")

def show_member_schedule(member_id):
    """회원의 스케줄 정보 출력"""
    member = MemberModel.get_member_by_id(member_id)
    if not member:
        print(f"ID {member_id}인 회원을 찾을 수 없습니다.")
        return
    
    schedule = ScheduleModel.get_member_schedule(member_id)
    
    print(f"\n회원: {member['name']} (ID: {member_id})")
    print(f"이메일: {member['email']}")
    print(f"목표: {member['goal']}")
    print(f"역할: {member['role']}")
    
    if not schedule:
        print("\n설정된 스케줄이 없습니다. (기본값: 평일 월~금)")
    else:
        weekdays = [ScheduleModel.get_weekday_name(day) for day in schedule]
        print(f"\n스케줄: {', '.join(weekdays)}")
        
        # 이번 주 날짜 표시
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        
        print("\n이번 주 스케줄:")
        print("-" * 50)
        print(f"{'요일':^10} | {'날짜':^12} | {'상태':^10}")
        print("-" * 50)
        
        for i in range(7):
            day = monday + timedelta(days=i)
            weekday = day.weekday()
            weekday_name = ScheduleModel.get_weekday_name(weekday)
            
            status = "예약됨" if weekday in schedule else "휴무일"
            if day < today:
                status = "지남"
            elif day == today:
                status = f"{status} (오늘)"
                
            print(f"{weekday_name:^10} | {day.strftime('%Y-%m-%d'):^12} | {status:^10}")

def set_schedule(member_id, weekdays):
    """회원의 스케줄 설정"""
    member = MemberModel.get_member_by_id(member_id)
    if not member:
        print(f"ID {member_id}인 회원을 찾을 수 없습니다.")
        return False
    
    if not weekdays:
        print("설정할 요일이 없습니다.")
        return False
    
    # 요일 번호 변환
    weekday_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
                  "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    
    schedule_days = []
    for day in weekdays:
        if day.isdigit() and 0 <= int(day) <= 6:
            schedule_days.append(int(day))
        elif day.lower() in weekday_map:
            schedule_days.append(weekday_map[day.lower()])
    
    # 중복 제거 및 정렬
    schedule_days = sorted(set(schedule_days))
    
    if not schedule_days:
        print("유효한 요일이 없습니다. 0-6 또는 요일 이름(월, 화, ..., 일 또는 mon, tue, ...)를 사용하세요.")
        return False
    
    # 스케줄 설정
    if ScheduleModel.set_member_schedule(member_id, schedule_days):
        weekday_names = [ScheduleModel.get_weekday_name(day) for day in schedule_days]
        print(f"회원 {member['name']}의 스케줄이 설정되었습니다: {', '.join(weekday_names)}")
        return True
    else:
        print(f"회원 {member['name']}의 스케줄 설정에 실패했습니다.")
        return False

def add_schedule_day(member_id, weekday):
    """회원의 스케줄에 요일 추가"""
    member = MemberModel.get_member_by_id(member_id)
    if not member:
        print(f"ID {member_id}인 회원을 찾을 수 없습니다.")
        return False
    
    # 요일 번호 변환
    weekday_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
                  "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    
    day_value = None
    if weekday.isdigit() and 0 <= int(weekday) <= 6:
        day_value = int(weekday)
    elif weekday.lower() in weekday_map:
        day_value = weekday_map[weekday.lower()]
    
    if day_value is None:
        print("유효한 요일이 아닙니다. 0-6 또는 요일 이름(월, 화, ..., 일 또는 mon, tue, ...)를 사용하세요.")
        return False
    
    # 요일 추가
    if ScheduleModel.add_schedule_day(member_id, day_value):
        weekday_name = ScheduleModel.get_weekday_name(day_value)
        print(f"회원 {member['name']}의 스케줄에 {weekday_name}이(가) 추가되었습니다.")
        return True
    else:
        print(f"회원 {member['name']}의 스케줄 추가에 실패했습니다.")
        return False

def remove_schedule_day(member_id, weekday):
    """회원의 스케줄에서 요일 제거"""
    member = MemberModel.get_member_by_id(member_id)
    if not member:
        print(f"ID {member_id}인 회원을 찾을 수 없습니다.")
        return False
    
    # 요일 번호 변환
    weekday_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
                  "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    
    day_value = None
    if weekday.isdigit() and 0 <= int(weekday) <= 6:
        day_value = int(weekday)
    elif weekday.lower() in weekday_map:
        day_value = weekday_map[weekday.lower()]
    
    if day_value is None:
        print("유효한 요일이 아닙니다. 0-6 또는 요일 이름(월, 화, ..., 일 또는 mon, tue, ...)를 사용하세요.")
        return False
    
    # 요일 제거
    if ScheduleModel.remove_schedule_day(member_id, day_value):
        weekday_name = ScheduleModel.get_weekday_name(day_value)
        print(f"회원 {member['name']}의 스케줄에서 {weekday_name}이(가) 제거되었습니다.")
        return True
    else:
        print(f"회원 {member['name']}의 스케줄 제거에 실패했습니다.")
        return False

def show_all_schedules():
    """모든 회원의 스케줄 정보 출력"""
    members = MemberModel.get_all_members()
    schedules = ScheduleModel.get_all_members_schedules()
    
    if not members:
        print("등록된 회원이 없습니다.")
        return
    
    print(f"\n총 {len(members)}명의 회원 스케줄:")
    print("-" * 100)
    print(f"{'ID':^5} | {'이름':^10} | {'이메일':^25} | {'역할':^8} | {'스케줄':^40}")
    print("-" * 100)
    
    for member in members:
        member_id = member['id']
        schedule = schedules.get(member_id, [])
        
        if not schedule:
            schedule_str = "기본값 (평일 월~금)"
        else:
            weekday_names = [ScheduleModel.get_weekday_name(day) for day in schedule]
            schedule_str = ", ".join(weekday_names)
        
        print(f"{member_id:^5} | {member['name']:^10} | {member['email']:^25} | {member['role']:^8} | {schedule_str:<40}")

def main():
    """스케줄 관리 메인 함수"""
    # 환경 변수 로드
    load_dotenv()
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="헬스장 회원 스케줄 관리 유틸리티")
    subparsers = parser.add_subparsers(dest="command", help="명령")
    
    # 회원 목록 명령
    list_parser = subparsers.add_parser("list", help="모든 회원 목록 조회")
    
    # 스케줄 조회 명령
    show_parser = subparsers.add_parser("show", help="회원의 스케줄 조회")
    show_parser.add_argument("member_id", type=int, help="회원 ID")
    
    # 스케줄 설정 명령
    set_parser = subparsers.add_parser("set", help="회원의 스케줄 설정")
    set_parser.add_argument("member_id", type=int, help="회원 ID")
    set_parser.add_argument("weekdays", nargs="+", help="요일 목록 (0-6 또는 월, 화, ..., 일 또는 mon, tue, ...)")
    
    # 스케줄 요일 추가 명령
    add_parser = subparsers.add_parser("add", help="회원의 스케줄에 요일 추가")
    add_parser.add_argument("member_id", type=int, help="회원 ID")
    add_parser.add_argument("weekday", help="추가할 요일 (0-6 또는 월, 화, ..., 일 또는 mon, tue, ...)")
    
    # 스케줄 요일 제거 명령
    remove_parser = subparsers.add_parser("remove", help="회원의 스케줄에서 요일 제거")
    remove_parser.add_argument("member_id", type=int, help="회원 ID")
    remove_parser.add_argument("weekday", help="제거할 요일 (0-6 또는 월, 화, ..., 일 또는 mon, tue, ...)")
    
    # 모든 회원 스케줄 조회 명령
    all_parser = subparsers.add_parser("all", help="모든 회원의 스케줄 조회")
    
    args = parser.parse_args()
    
    # 명령 처리
    if args.command == "list":
        list_members()
    elif args.command == "show":
        show_member_schedule(args.member_id)
    elif args.command == "set":
        set_schedule(args.member_id, args.weekdays)
    elif args.command == "add":
        add_schedule_day(args.member_id, args.weekday)
    elif args.command == "remove":
        remove_schedule_day(args.member_id, args.weekday)
    elif args.command == "all":
        show_all_schedules()
    else:
        parser.print_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}", exc_info=True)
        print(f"오류 발생: {str(e)}")
        sys.exit(1) 