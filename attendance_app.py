"""
헬스장 회원 출석률 알림 애플리케이션
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
import random
from typing import Dict, List, Tuple, Optional, Any
import json

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, messaging
import psycopg2
from psycopg2 import extras

# OpenAI 및 LangChain 임포트
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gym_attendance_agent.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 디렉토리 추가
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from langgraph.attendance_agent import create_attendance_workflow
from langgraph.attendance_agent.prompts import (
    get_praise_prompt,
    get_encouragement_prompt,
    get_motivation_prompt
)

# PostgreSQL 데이터베이스 연결 설정
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "gym")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")

# Firebase 초기화 (서비스 계정 키가 있는 경우에만)
firebase_initialized = False
try:
    service_account_path = "firebase-service-account-key.json"
    if os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase 초기화 성공")
    else:
        logger.warning(f"Firebase 서비스 계정 키 파일({service_account_path})을 찾을 수 없습니다. FCM 기능이 비활성화됩니다.")
except Exception as e:
    logger.error(f"Firebase 초기화 중 오류 발생: {str(e)}")

# OpenAI API 키 확인
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. LLM 기능이 제한됩니다.")

# LLM 모델 초기화
llm = ChatOpenAI(
    api_key=openai_api_key,
    model="gpt-3.5-turbo-0125",
    temperature=0.9
)
logger.info("OpenAI LLM 모델이 초기화되었습니다. (temperature=0.9로 다양성 증가)")

def get_db_connection():
    """
    PostgreSQL 데이터베이스 연결을 생성합니다.
    
    Returns:
        connection: 데이터베이스 연결 객체
    """
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info("데이터베이스 연결 성공")
        return connection
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {str(e)}")
        return None

def get_user_data(user_id):
    """
    사용자 데이터를 PostgreSQL 데이터베이스에서 가져오는 함수
    
    Args:
        user_id: 사용자 ID
        
    Returns:
        dict: 사용자 정보 딕셔너리 또는 찾지 못한 경우 None
    """
    # 디버그 로그 추가
    logger.info(f"get_user_data 함수 호출됨: user_id={user_id}, 타입={type(user_id)}")
    
    # ID가 숫자인 경우 처리
    try:
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
            logger.info(f"숫자 ID 변환: user_id={user_id}")
    except Exception as e:
        logger.error(f"ID 변환 중 오류: {str(e)}")
    
    # 데이터베이스 연결
    conn = get_db_connection()
    if not conn:
        logger.error("데이터베이스 연결을 만들 수 없습니다.")
        return None
    
    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cursor:
            # member 테이블에서 사용자 정보 조회
            query = "SELECT id, name, email, fcm_token, role, goal FROM member WHERE id = %s"
            params = (user_id,)
            logger.info(f"사용자 정보 조회 쿼리: {query}, 파라미터: {params}")
            
            cursor.execute(query, params)
            
            user_record = cursor.fetchone()
            
            if user_record:
                logger.info(f"사용자 레코드 발견: {dict(user_record)}")
                
                # 스케줄 기반 출석률 계산 전에 먼저 member_schedule 테이블 확인
                cursor.execute(
                    "SELECT COUNT(*) FROM member_schedule WHERE member_id = %s AND is_active = true",
                    (user_record["id"],)
                )
                schedule_count = cursor.fetchone()[0]
                logger.info(f"활성화된 스케줄 수: {schedule_count}")
                
                # 일반 출석률 계산 (기존 방식, 스케줄 테이블이 없거나 오류 발생 시 사용)
                if schedule_count == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as count 
                        FROM attendance 
                        WHERE member_id = %s AND attendance_date >= current_date - INTERVAL '7 days'
                        AND status = '출석'
                    """, (user_record["id"],))
                    
                    attendance_result = cursor.fetchone()
                    attended_count = attendance_result["count"] if attendance_result else 0
                    total_scheduled = 7
                    
                    # 출석률 계산
                    attendance_rate = min(100, int((attended_count * 100) / total_scheduled))
                    
                    logger.info(f"일반 출석률 계산 (스케줄 없음): {attended_count}/{total_scheduled} = {attendance_rate}%")
                else:
                    try:
                        # 출석률 계산 (스케줄 기반으로 수정)
                        cursor.execute("""
                            WITH days_with_schedule AS (
                                SELECT DISTINCT weekday
                                FROM member_schedule
                                WHERE member_id = %s AND is_active = true
                            ),
                            last_7_days AS (
                                SELECT date_trunc('day', (current_date - offs)) AS day_date,
                                EXTRACT(DOW FROM (current_date - offs)) AS day_of_week
                                FROM generate_series(0, 6) AS offs
                            ),
                            scheduled_days AS (
                                SELECT l.day_date
                                FROM last_7_days l
                                JOIN days_with_schedule d ON l.day_of_week = d.weekday
                            ),
                            attendance_days AS (
                                SELECT COUNT(DISTINCT attendance_date) AS attended_count
                                FROM attendance
                                WHERE member_id = %s 
                                AND attendance_date >= current_date - INTERVAL '7 days'
                                AND attendance_date <= current_date
                                AND status = '출석'
                            ),
                            total_scheduled AS (
                                SELECT COUNT(*) AS total_count FROM scheduled_days
                            )
                            SELECT 
                                COALESCE(ad.attended_count, 0) AS attended,
                                CASE 
                                    WHEN COALESCE(ts.total_count, 0) = 0 THEN 0
                                    ELSE COALESCE(ad.attended_count, 0)
                                END AS attended_count,
                                COALESCE(ts.total_count, 0) AS total_scheduled
                            FROM total_scheduled ts
                            CROSS JOIN attendance_days ad
                        """, (user_record["id"], user_record["id"]))
                        
                        attendance_result = cursor.fetchone()
                        logger.info(f"출석률 계산 결과: {dict(attendance_result) if attendance_result else None}")
                        
                        attended_count = attendance_result["attended_count"] if attendance_result else 0
                        total_scheduled = max(1, attendance_result["total_scheduled"] if attendance_result else 7)
                        
                        # 출석률 계산 (스케줄 기반)
                        attendance_rate = min(100, int((attended_count * 100) / total_scheduled))
                        
                        logger.info(f"스케줄 기반 출석률 계산: {attended_count}/{total_scheduled} = {attendance_rate}%")
                    except Exception as e:
                        logger.error(f"스케줄 기반 출석률 계산 중 오류: {str(e)}")
                        # 오류 시 기본 방식으로 계산
                        cursor.execute("""
                            SELECT COUNT(*) as count 
                            FROM attendance 
                            WHERE member_id = %s AND attendance_date >= current_date - INTERVAL '7 days'
                            AND status = '출석'
                        """, (user_record["id"],))
                        
                        attendance_result = cursor.fetchone()
                        attended_count = attendance_result["count"] if attendance_result else 0
                        total_scheduled = 7
                        
                        # 출석률 계산
                        attendance_rate = min(100, int((attended_count * 100) / total_scheduled))
                        
                        logger.info(f"대체 출석률 계산: {attended_count}/{total_scheduled} = {attendance_rate}%")
                
                # DB에서 가져온 정보를 딕셔너리로 변환
                user_data = {
                    "name": user_record["name"],
                    "attendance_rate": attendance_rate,
                    "personal_goal": user_record["goal"],
                    "fcm_token": user_record["fcm_token"]
                }
                logger.info(f"DB에서 사용자 데이터 찾음: {user_data}")
                return user_data
            else:
                logger.warning(f"DB에서 사용자 '{user_id}'에 대한 데이터를 찾을 수 없습니다.")
                return None
                
    except Exception as e:
        logger.error(f"사용자 데이터 조회 중 오류: {str(e)}")
        return None
    finally:
        conn.close()

def get_all_user_ids():
    """
    데이터베이스에서 모든 사용자 ID를 가져옵니다.
    
    Returns:
        list: 사용자 ID 목록
    """
    # 데이터베이스 연결
    conn = get_db_connection()
    if not conn:
        logger.error("데이터베이스 연결을 만들 수 없습니다.")
        return []
    
    try:
        with conn.cursor() as cursor:
            # member 테이블에서 모든 사용자 ID 조회
            cursor.execute("SELECT id FROM member")
            user_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"DB에서 가져온 사용자 ID 목록: {user_ids}")
            return user_ids
    except Exception as e:
        logger.error(f"사용자 ID 목록 조회 중 오류: {str(e)}")
        return []
    finally:
        conn.close()

def generate_notification_message(user_id, attendance_rate, personal_goal):
    """
    출석률과 개인 목표에 따른 맞춤형 알림 메시지 생성
    
    Args:
        user_id: 사용자 ID
        attendance_rate: 출석률 (%)
        personal_goal: 개인 목표
        
    Returns:
        str: 생성된 알림 메시지
    """
    user_data = get_user_data(user_id)
    name = user_data.get("name", user_id) if user_data else user_id
    
    logger.info(f"메시지 생성 시작 - 이름: {name}, 출석률: {attendance_rate}, 목표: {personal_goal}")
    
    # JSON 출력 파서 설정
    parser = JsonOutputParser()
    
    try:
        # 출석률에 따른 메시지 유형 결정
        if attendance_rate >= 80:
            # 우수 회원
            prompt = get_praise_prompt()
            chain = prompt | ChatOpenAI(temperature=0.9) | parser
            result = chain.invoke({"name": name, "personal_goal": personal_goal})
            message = result.get("message", "")
        elif attendance_rate >= 60:
            # 보통 회원
            prompt = get_encouragement_prompt()
            chain = prompt | ChatOpenAI(temperature=0.9) | parser
            result = chain.invoke({"name": name, "personal_goal": personal_goal})
            message = result.get("message", "")
        else:
            # 저조 회원
            prompt = get_motivation_prompt()
            chain = prompt | ChatOpenAI(temperature=0.9) | parser
            result = chain.invoke({"name": name, "personal_goal": personal_goal})
            message = result.get("message", "")
            
        logger.info(f"LLM으로 생성된 메시지: {message}")
        return message
        
    except Exception as e:
        logger.error(f"메시지 생성 중 오류: {str(e)}")
        # 오류 발생 시 기본 메시지 반환
        if attendance_rate >= 80:
            return f"{name}님, 정말 대단해요! 목표를 향해 꾸준히 나아가고 계시네요. 지금처럼 계속 유지하시면 좋은 결과가 있을 거예요!"
        elif attendance_rate >= 60:
            return f"{name}님, 안녕하세요! '{personal_goal}'을 위해 노력하고 계시네요. 조금만 더 자주 방문하시면 더 빠른 결과를 얻으실 수 있을 거예요!"
        else:
            return f"{name}님, 오랜만이에요! 최근에 바쁘신가요? 이번 주에 헬스장에 들러 운동 루틴을 되찾아보는 건 어떨까요?"

def send_push_notification(token, title, body, data=None):
    """
    FCM을 통해 푸시 알림 전송
    
    Args:
        token: FCM 토큰
        title: 알림 제목
        body: 알림 내용
        data: 추가 데이터 (선택 사항)
    
    Returns:
        성공 여부
    """
    if not firebase_initialized:
        logger.warning("Firebase가 초기화되지 않아 푸시 알림을 보낼 수 없습니다.")
        return False
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=token
        )
        
        response = messaging.send(message)
        logger.info(f"메시지 전송 성공: {response}")
        return True
    except Exception as e:
        logger.error(f"메시지 전송 실패: {e}")
        return False

def process_user(user_id: str, workflow=None, fcm_token=None) -> str:
    """
    특정 사용자의 알림을 처리합니다.
    
    Args:
        user_id: 사용자 ID
        workflow: 워크플로우 객체 (선택 사항)
        fcm_token: FCM 토큰 (선택 사항)
        
    Returns:
        str: 생성된 메시지
    """
    try:
        logger.info(f"알림 처리 시작 - 사용자 ID: {user_id}, FCM 토큰 제공 여부: {fcm_token is not None}")
        
        # 사용자 ID 유효성 검사
        if not user_id:
            logger.error("사용자 ID가 제공되지 않았습니다.")
            return "사용자 ID가 필요합니다."
            
        # 사용자 데이터 가져오기
        user_data = get_user_data(user_id)
        if not user_data:
            logger.error(f"사용자 데이터를 찾을 수 없음: {user_id}")
            return f"사용자 데이터를 찾을 수 없습니다: {user_id}"
            
        name = user_data.get("name", user_id)
        attendance_rate = user_data.get("attendance_rate", 0)
        personal_goal = user_data.get("personal_goal", "일반")
        
        # FCM 토큰이 제공되지 않은 경우 사용자 데이터에서 가져옴
        if not fcm_token and "fcm_token" in user_data and user_data["fcm_token"]:
            fcm_token = user_data["fcm_token"]
            logger.info(f"사용자 데이터에서 FCM 토큰을 가져왔습니다: {fcm_token[:10]}...")
        
        logger.info(f"사용자 정보 - 이름: {name}, 출석률: {attendance_rate}, 목표: {personal_goal}")
        
        # 알림 메시지 생성
        message = generate_notification_message(user_id, attendance_rate, personal_goal)
        logger.info(f"생성된 메시지: {message}")
        
        # FCM 토큰이 있고 Firebase가 초기화된 경우 푸시 알림 전송
        if fcm_token and firebase_initialized:
            logger.info("푸시 알림 전송 시도")
            success = send_push_notification(
                token=fcm_token,
                title="헬스장 출석 알림",
                body=message,
                data={"user_id": str(user_id)}
            )
            
            if success:
                logger.info("푸시 알림 전송 성공")
            else:
                logger.warning("푸시 알림 전송 실패")
        elif fcm_token and not firebase_initialized:
            logger.warning("Firebase가 초기화되지 않아 푸시 알림을 보낼 수 없습니다.")
        else:
            logger.info("FCM 토큰이 제공되지 않아 푸시 알림을 보내지 않습니다.")
        
        return message
    except Exception as e:
        logger.error(f"알림 처리 중 오류: {str(e)}")
        return f"알림 처리 중 오류가 발생했습니다: {str(e)}"

def process_all_users(workflow=None, send_notifications=True):
    """
    모든 사용자에 대한 알림을 처리합니다.
    
    Args:
        workflow: 워크플로우 객체 (선택 사항)
        send_notifications: 알림 전송 여부
        
    Returns:
        dict: 사용자별 결과
    """
    try:
        logger.info("모든 사용자 알림 처리 시작")
        
        # 사용자 ID 목록 가져오기
        user_ids = get_all_user_ids()
        
        if not user_ids:
            logger.warning("처리할 사용자가 없습니다.")
            return {"error": "처리할 사용자가 없습니다."}
        
        results = {}
        for user_id in user_ids:
            logger.info(f"사용자 처리 중: {user_id}")
            message = process_user(user_id)
            results[user_id] = message
        
        logger.info(f"총 {len(results)} 명의 사용자 처리 완료")
        return results
    
    except Exception as e:
        logger.error(f"전체 사용자 처리 중 오류: {str(e)}")
        return {"error": str(e)}

def parse_arguments():
    """
    명령줄 인자 파싱
    
    Returns:
        argparse.Namespace: 파싱된 인자
    """
    parser = argparse.ArgumentParser(
        description="헬스장 출석률 알림 워크플로우",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python attendance_app.py --id 1            # user1 회원에게 알림 전송
  python attendance_app.py --id user2        # user2 회원에게 알림 전송
  python attendance_app.py --all             # 모든 회원에게 알림 전송
"""
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=str, help="알림을 보낼 회원 ID (예: user1 또는 1)")
    group.add_argument("--all", action="store_true", help="모든 회원에게 알림 전송")
    
    # 인자가 없으면 도움말 표시
    if len(sys.argv) == 1:
        parser.print_help()
        return None
        
    return parser.parse_args()

def run_app():
    """
    애플리케이션 실행
    
    Returns:
        int: 종료 코드
    """
    args = parse_arguments()
    if args is None:
        return 1
    
    if args.id:
        user_id = args.id
        # 숫자만 입력한 경우 user 접두사 추가
        if user_id.isdigit():
            user_id = f"user{user_id}"
            
        logger.info(f"헬스장 회원 {user_id}에 대한 출석률 알림 워크플로우 시작")
        process_user(user_id)
    elif args.all:
        process_all_users()
    
    return 0

# 프로그램 진입점
if __name__ == "__main__":
    sys.exit(run_app()) 