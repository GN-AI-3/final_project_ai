"""
헬스장 출석률 기반 알림 에이전트의 노드 구현
"""
import logging
import os
from typing import Dict, List, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

from .prompts import get_praise_prompt, get_encouragement_prompt, get_motivation_prompt

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger(__name__)

# PostgreSQL 데이터베이스 연결 설정
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "gym")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")

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

def get_user_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 데이터를 가져오는 노드
    """
    user_id = state["user_id"]
    logger.info(f"헬스장 회원 {user_id}의 데이터를 가져오는 중..., 타입={type(user_id)}")
    
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
        return {
            "user_id": user_id,
            "user_found": False
        }
    
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
                    "email": user_record["email"],
                    "fcm_token": user_record["fcm_token"]
                }
                
                logger.info(f"DB에서 사용자 데이터 찾음: {user_data}")
                logger.info(f"헬스장 회원 {user_id} 데이터 조회 완료: 출석률 {attendance_rate}%")
                
                return {
                    "user_id": user_id,
                    "user_found": True,
                    "user_data": user_data
                }
            else:
                logger.warning(f"DB에서 사용자 '{user_id}'에 대한 데이터를 찾을 수 없습니다.")
                return {
                    "user_id": user_id,
                    "user_found": False
                }
                
    except Exception as e:
        logger.error(f"사용자 데이터 조회 중 오류: {str(e)}")
        return {
            "user_id": user_id,
            "user_found": False
        }
    finally:
        conn.close()

def analyze_attendance(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    출석률을 분석하고 알림 필요성을 판단하는 노드
    """
    if not state.get("user_found", False):
        logger.warning("헬스장 회원을 찾을 수 없어 출석률 분석을 건너뜁니다.")
        return {**state, "send_notification": False}
    
    user_data = state["user_data"]
    attendance_rate = user_data["attendance_rate"]
    
    # 출석률 기준에 따른 상태 분류
    if attendance_rate >= 80:
        status = "excellent"
        message_type = "praise"
    elif attendance_rate >= 45:
        status = "good"
        message_type = "encouragement"
    else:
        status = "needs_improvement"
        message_type = "motivation"
    
    logger.info(f"헬스장 회원 {state['user_id']}의 출석률 분석 결과: {status}")
    
    return {
        **state,
        "attendance_status": status,
        "message_type": message_type,
        "send_notification": True
    }

def create_notification(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    출석률과 개인 목표에 기반한 맞춤형 알림 메시지 생성 노드
    """
    if not state.get("send_notification", False):
        logger.info("알림이 필요하지 않습니다.")
        return {**state, "notifications": []}
    
    user_data = state["user_data"]
    message_type = state["message_type"]
    
    # LLM을 사용하여 맞춤형 메시지 생성
    llm = ChatOpenAI(temperature=0.9)  # 더 다양한 응답을 위해 temperature 값을 0.9로 설정
    parser = JsonOutputParser()
    
    # 메시지 유형별 프롬프트 가져오기
    if message_type == "praise":
        prompt = get_praise_prompt()
    elif message_type == "encouragement":
        prompt = get_encouragement_prompt()
    else:  # "motivation"
        prompt = get_motivation_prompt()
    
    # 프롬프트 생성 및 LLM 호출
    chain = prompt | llm | parser
    
    result = chain.invoke(user_data)
    notification_message = result.get("message", "")
    
    logger.info(f"헬스장 회원 {state['user_id']}에게 보낼 알림 메시지 생성 완료")
    
    return {
        **state,
        "notifications": [notification_message]
    }

def deliver_notification(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    생성된 알림을 사용자에게 전달하는 노드
    """
    if not state.get("notifications"):
        logger.info("전달할 알림이 없습니다.")
        return {**state, "delivery_results": []}
    
    notifications = state["notifications"]
    user_data = state.get("user_data", {})
    email = user_data.get("email", "")
    
    delivery_results = []
    
    for i, notification in enumerate(notifications, 1):
        # 실제 구현에서는 이메일 또는 푸시 알림 서비스를 호출
        logger.info(f"알림 {i}를 {email}로 전송 중...")
        
        # 알림 전송 성공 시뮬레이션 (실제 구현에서는 실제 전송 로직으로 대체)
        success = True
        
        delivery_results.append({
            "index": i,
            "success": success,
            "notification": notification,
            "recipient": email
        })
        
        logger.info(f"알림 {i} 전송 {'성공' if success else '실패'}")
    
    return {
        **state,
        "delivery_results": delivery_results
    } 