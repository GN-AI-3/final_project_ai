"""
헬스장 회원 출석 알림을 위한 도구 모음
"""
import logging
import json
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from notification.database.connection import get_db_connection
from notification.langchain.prompts import get_praise_prompt, get_encouragement_prompt, get_motivation_prompt

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@tool
def get_user_data(user_id: str) -> Dict[str, Any]:
    """
    특정 회원의 데이터를 조회합니다.
    
    Args:
        user_id: 조회할 회원 ID (이메일)
        
    Returns:
        Dict: 회원 데이터
    """
    try:
        logger.info(f"회원 데이터 조회 시작: {user_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 회원 기본 정보 조회
        cursor.execute("""
            SELECT email, name, email, fcm_token, phone
            FROM member
            WHERE email = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            logger.warning(f"회원을 찾을 수 없음: {user_id}")
            return {"error": "회원을 찾을 수 없습니다."}
            
        logger.info(f"회원 정보 조회 성공: {user[1]}")
        
        # 회원 목표 조회
        cursor.execute("""
            SELECT goal
            FROM member_goal_list
            WHERE email = %s
        """, (user_id,))
        
        goal_row = cursor.fetchone()
        personal_goal = "건강 유지"  # 기본값
        
        if goal_row:
            # 목표 타입을 사용자 친화적인 메시지로 변환
            goal_type = goal_row[0]
            if goal_type == "WEIGHT_LOSS":
                personal_goal = "체중 감량"
            elif goal_type == "STRENGTH":
                personal_goal = "신체 능력 강화"
            elif goal_type == "MENTAL_HEALTH":
                personal_goal = "정신적 건강 관리"
            elif goal_type == "HEALTH_MAINTENANCE":
                personal_goal = "건강 유지"
            elif goal_type == "BODY_SHAPE":
                personal_goal = "체형 관리"
            elif goal_type == "HOBBY":
                personal_goal = "취미"
            else:
                personal_goal = goal_type  # 알 수 없는 유형은 그대로 사용
        
        # 출석률 계산 (invoke 메서드 사용)
        attendance_rate = get_attendance_rate.invoke(user_id)
        
        return {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "fcm_token": user[3],
            "personal_goal": personal_goal,
            "attendance_rate": attendance_rate
        }
        
    except Exception as e:
        logger.error(f"회원 데이터 조회 중 오류: {str(e)}")
        return {"error": str(e)}
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@tool
def get_all_user_ids(unused_input: str = "") -> List[str]:
    """
    모든 회원의 ID를 조회합니다.
    
    Returns:
        List[str]: 회원 ID 목록 (이메일)
    """
    try:
        logger.info("모든 회원 ID 조회 시작")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email
            FROM member
        """)
        
        user_ids = [row[0] for row in cursor.fetchall()]
        logger.info(f"{len(user_ids)}명의 회원 ID 조회 완료")
        return user_ids
        
    except Exception as e:
        logger.error(f"회원 ID 목록 조회 중 오류: {str(e)}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@tool
def get_attendance_rate(user_id: str) -> float:
    """
    특정 회원의 출석률을 계산합니다. 최근 일주일 스케줄 기준으로 계산합니다.
    
    Args:
        user_id: 회원 ID (이메일)
        
    Returns:
        float: 출석률 (0-100)
    """
    try:
        logger.info(f"출석률 계산 시작: 회원 ID {user_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 최근 7일간의 스케줄 및 출석 상태 조회
        cursor.execute("""
            WITH days_with_schedule AS (
                SELECT DISTINCT day_of_week
                FROM schedule
                WHERE member_id = %s AND active = true
            ),
            last_7_days AS (
                SELECT date_trunc('day', (current_date - offs)) AS day_date,
                EXTRACT(DOW FROM (current_date - offs)) AS day_of_week
                FROM generate_series(0, 6) AS offs
            ),
            scheduled_days AS (
                SELECT l.day_date
                FROM last_7_days l
                JOIN days_with_schedule d ON l.day_of_week = d.day_of_week
            ),
            attendance_days AS (
                SELECT COUNT(DISTINCT attendance_date) AS attended_count
                FROM attendance
                WHERE member_id = %s 
                AND attendance_date >= current_date - INTERVAL '7 days'
                AND attendance_date <= current_date
                AND status = 'PRESENT'
            ),
            total_scheduled AS (
                SELECT COUNT(*) AS total_count FROM scheduled_days
            )
            SELECT 
                COALESCE(ad.attended_count, 0) AS attended,
                COALESCE(ts.total_count, 0) AS total_scheduled
            FROM total_scheduled ts
            CROSS JOIN attendance_days ad
        """, (user_id, user_id))
        
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"회원 ID {user_id}의 출석 데이터를 찾을 수 없습니다.")
            return 0.0
            
        attended = result[0]
        total_scheduled = result[1]
        
        if total_scheduled == 0:
            logger.warning(f"회원 ID {user_id}의 최근 7일 예정된 스케줄이 없습니다.")
            return 0.0
            
        # 출석률 계산
        attendance_rate = min(100.0, (attended * 100) / total_scheduled)
        logger.info(f"회원 ID {user_id}의 출석률: {attendance_rate:.2f}% (출석: {attended}, 예정: {total_scheduled})")
        
        return attendance_rate
        
    except Exception as e:
        logger.error(f"출석률 계산 중 오류: {str(e)}")
        return 0.0
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@tool
def send_push_notification(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    특정 회원에게 푸시 알림을 보냅니다.
    
    Args:
        input_data: 푸시 알림 데이터
            user_id: 회원 ID
            message: 알림 메시지
            fcm_token: FCM 토큰
        
    Returns:
        Dict: 전송 결과
    """
    try:
        # 필수 데이터 확인
        if not isinstance(input_data, dict):
            return {"error": "입력 데이터는 딕셔너리 형태여야 합니다."}
        
        # 입력 데이터 추출
        user_id = input_data.get("user_id")
        message = input_data.get("message")
        fcm_token = input_data.get("fcm_token")
        
        if not user_id or not message:
            return {"error": "회원 ID와 메시지는 필수 항목입니다."}
        
        logger.info(f"푸시 알림 전송 시작: 회원 ID {user_id}")
        
        # FCM 초기화 확인
        try:
            from firebase_admin import messaging
            if not fcm_token:
                logger.warning("FCM 토큰이 없어 푸시 알림을 보낼 수 없습니다.")
                return {
                    "success": False,
                    "message": "FCM 토큰이 없습니다."
                }
                
            # 메시지 구성
            message_data = messaging.Message(
                notification=messaging.Notification(
                    title='헬스장 출석 알림',
                    body=message,
                ),
                data={
                    'user_id': str(user_id),
                    'title': '헬스장 출석 알림',
                    'body': message,
                    'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                },
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        priority='high',
                        channel_id='high_importance_channel'
                    )
                ),
                apns=messaging.APNSConfig(
                    headers={
                        'apns-priority': '10',
                    },
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title='헬스장 출석 알림',
                                body=message
                            ),
                            sound='default',
                            badge=1
                        )
                    )
                ),
                token=fcm_token,
            )
            
            # 메시지 전송
            response = messaging.send(message_data)
            logger.info(f"FCM 메시지 전송 성공: {response}")
            
            return {
                "success": True,
                "message": "알림이 성공적으로 전송되었습니다.",
                "response": response
            }
            
        except ImportError:
            logger.warning("Firebase Admin SDK가 설치되어 있지 않아 푸시 알림을 보낼 수 없습니다.")
            return {
                "success": False,
                "message": "Firebase Admin SDK가 설치되어 있지 않습니다."
            }
        except Exception as e:
            logger.error(f"FCM 메시지 전송 중 오류: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
            
    except Exception as e:
        logger.error(f"푸시 알림 전송 중 오류: {str(e)}")
        return {"error": str(e)}

@tool
def generate_notification_message(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 데이터를 기반으로 개인화된 알림 메시지를 생성합니다.
    
    Args:
        input_data: 입력 데이터
            user_data: 사용자 데이터 (name, attendance_rate, personal_goal 등 포함)
            
    Returns:
        Dict: 생성된 메시지
    """
    try:
        # 필수 데이터 확인
        if not isinstance(input_data, dict):
            return {"error": "입력 데이터는 딕셔너리 형태여야 합니다."}
            
        user_data = input_data.get("user_data")
        if not user_data or not isinstance(user_data, dict):
            return {"error": "사용자 데이터가 올바르지 않습니다."}
            
        # 사용자 정보 추출
        name = user_data.get("name", "회원")
        attendance_rate = user_data.get("attendance_rate", 0.0)
        goal = user_data.get("personal_goal", "건강 유지")
        
        logger.info(f"알림 메시지 생성: {name}, 출석률: {attendance_rate:.1f}%, 목표: {goal}")
        
        # LLM 초기화
        llm = ChatOpenAI(
            model="gpt-4o-mini", 
            temperature=0.9,  # 다양한 응답을 위해 온도 높임
            timeout=10
        )
        
        # 출석률에 따라 다른 프롬프트 선택 및 포매팅
        if attendance_rate >= 70:
            prompt = get_praise_prompt()
        elif attendance_rate >= 40:
            prompt = get_encouragement_prompt()
        else:
            prompt = get_motivation_prompt()
        
        # 매개변수를 직접 전달 (personal_goal → goal로 매핑)
        chain = prompt | llm
        response = chain.invoke({"name": name, "goal": goal})
        
        # 응답 처리
        message = response.content.strip()
        
        # JSON 형식이나 마크다운 형식이 포함된 경우 제거
        import re
        
        # 코드 블록, 백틱 제거
        message = re.sub(r'```(?:json)?|```', '', message)
        
        # JSON 형식 객체 패턴 찾기
        json_pattern = re.search(r'{\s*"message"\s*:\s*"(.+?)"\s*}', message)
        if json_pattern:
            # JSON 객체 내 message 값만 추출
            message = json_pattern.group(1)
        
        # 따옴표나 불필요한 공백 제거
        message = message.strip('"\'').strip()
            
        # 너무 긴 메시지는 자르기
        if len(message) > 200:
            message = message[:197] + "..."
            
        logger.info(f"생성된 메시지: {message}")
        
        return {
            "message": message,
            "attendance_rate": attendance_rate
        }
        
    except Exception as e:
        logger.error(f"메시지 생성 중 오류: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)} 