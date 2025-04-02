"""
헬스장 회원 출석 알림을 위한 Agent 모듈
"""
import logging
import os
import json
from typing import Dict, Optional, List, Any

from langchain_openai import ChatOpenAI

from notification.langchain.tools import (
    get_user_data,
    get_all_user_ids,
    send_push_notification,
    get_attendance_rate,
    generate_notification_message
)
from notification.database.connection import get_db_connection

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Firebase 초기화 (선택적)
firebase_initialized = False
try:
    # Firebase Admin SDK가 설치되어 있는지 확인
    import firebase_admin
    from firebase_admin import credentials, messaging
    
    # 서비스 계정 키 파일 경로 확인 (여러 가능한 파일명 시도)
    possible_service_account_paths = [
        os.environ.get('FIREBASE_SERVICE_ACCOUNT'),  # 환경 변수
        'firebase-service-account-key.json',         # 하이픈 포함 파일명
        'serviceAccountKey.json',                    # 기본 파일명
        'service-account-key.json'                   # 또 다른 일반적인 파일명
    ]
    
    # 가능한 파일 경로 중 존재하는 파일 찾기
    service_account_path = None
    for path in possible_service_account_paths:
        if path and os.path.exists(path):
            service_account_path = path
            break
    
    if service_account_path:
        try:
            # 이미 초기화되었는지 확인
            app = firebase_admin.get_app()
            firebase_initialized = True
            logger.info("Firebase가 이미 초기화되어 있습니다.")
        except ValueError:
            # Firebase 초기화
            try:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                firebase_initialized = True
                logger.info(f"Firebase가 성공적으로 초기화되었습니다. (키 파일: {service_account_path})")
            except Exception as e:
                logger.warning(f"Firebase 초기화 실패: {str(e)}")
    else:
        logger.warning(f"Firebase 서비스 계정 키 파일을 찾을 수 없습니다. 다음 경로를 시도했습니다: {possible_service_account_paths}")
except ImportError:
    logger.warning("firebase-admin 패키지가 설치되어 있지 않습니다. FCM 기능이 비활성화됩니다.")

def process_user_notification(user_id: str, update_fcm_token: Optional[str] = None) -> Dict[str, Any]:
    """
    특정 회원에게 알림 메시지를 생성하고 처리합니다.
    
    Args:
        user_id: 처리할 회원 ID
        update_fcm_token: 업데이트할 FCM 토큰 (선택 사항)
    
    Returns:
        Dict: 처리 결과
    """
    try:
        logger.info(f"회원 알림 처리 시작: {user_id}")
        
        # 회원 데이터 조회
        user_data = get_user_data.invoke(user_id)
        
        # 에러 확인
        if "error" in user_data:
            logger.error(f"회원 데이터 조회 실패: {user_data['error']}")
            return {
                "success": False,
                "user_id": user_id,
                "error": user_data["error"]
            }
        
        # FCM 토큰 업데이트 처리
        if update_fcm_token:
            user_data["fcm_token"] = update_fcm_token
            logger.info(f"FCM 토큰 업데이트: {user_id}")
            
            # 데이터베이스에 FCM 토큰 업데이트
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE member
                    SET fcm_token = %s,
                        modified_at = CURRENT_TIMESTAMP
                    WHERE email = %s
                """, (update_fcm_token, user_id))
                conn.commit()
                logger.info(f"회원 ID {user_id}의 FCM 토큰이 데이터베이스에 업데이트되었습니다.")
            except Exception as e:
                logger.error(f"FCM 토큰 데이터베이스 업데이트 실패: {str(e)}")
            finally:
                if 'conn' in locals() and conn:
                    conn.close()
        
        # 알림 메시지 생성
        notification_result = generate_notification_message.invoke({"input_data": {"user_data": user_data}})
        
        # 에러 확인
        if "error" in notification_result:
            logger.error(f"알림 메시지 생성 실패: {notification_result['error']}")
            return {
                "success": False,
                "user_id": user_id,
                "user_name": user_data.get("name", "알 수 없음"),
                "error": notification_result["error"]
            }
        
        message = notification_result.get("message", "")
        
        # 결과 구성
        result = {
            "success": True,
            "user_id": user_id,
            "message": message,
            "user_name": user_data.get("name", "알 수 없음"),
            "personal_goal": user_data.get("personal_goal", ""),
            "attendance_rate": user_data.get("attendance_rate", 0.0),
            "notification_sent": False
        }
        
        # FCM 토큰이 있으면 알림 전송
        if user_data.get("fcm_token"):
            send_data = {
                "input_data": {
                    "user_id": user_id,
                    "message": message,
                    "fcm_token": user_data["fcm_token"]
                }
            }
            push_result = send_push_notification.invoke(send_data)
            
            result["notification_sent"] = push_result.get("success", False)
            if not push_result.get("success", False):
                result["notification_error"] = push_result.get("message", "알림 전송 실패")
                
        logger.info(f"회원 알림 처리 완료: {user_id}, 메시지 생성: {bool(message)}, 알림 전송: {result['notification_sent']}")
        return result
        
    except Exception as e:
        logger.error(f"회원 알림 처리 중 오류: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }

def process_all_users(update_fcm_token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    모든 회원에게 알림을 처리합니다.
    
    Args:
        update_fcm_token: 업데이트할 FCM 토큰 (선택 사항)
    
    Returns:
        List[Dict]: 처리 결과 목록
    """
    try:
        logger.info("전체 회원 알림 처리 시작")
        
        # 모든 회원 ID 조회
        user_ids = get_all_user_ids.invoke("")
        
        if not user_ids:
            logger.warning("처리할 회원이 없습니다.")
            return []
        
        results = []
        for user_id in user_ids:
            # 각 회원별 알림 처리
            result = process_user_notification(user_id, update_fcm_token)
            results.append(result)
            
        logger.info(f"전체 회원 알림 처리 완료: {len(results)}명")
        return results
        
    except Exception as e:
        logger.error(f"전체 회원 알림 처리 중 오류: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return [{"success": False, "error": str(e)}] 