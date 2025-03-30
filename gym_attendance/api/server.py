"""
헬스장 출석률 알림 시스템 FastAPI 서버
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging

# 새로운 모듈 구조로 임포트
from gym_attendance.notification.agent import process_user_notification, process_all_users
from gym_attendance.notification.tools import (
    get_user_data,
    get_all_user_ids
)
from gym_attendance.database.connection import get_db_connection
from gym_attendance.utils.logging import setup_logger
from gym_attendance.api.models import (
    NotificationResponse,
    UserResponse,
    UserListResponse,
    NotificationItem,
    AllNotificationsResponse
)

# 로거 설정
logger = setup_logger(__name__)

def create_app():
    """FastAPI 앱을 생성하고 설정합니다."""
    
    # FastAPI 앱 생성
    app = FastAPI(
        title="헬스장 출석률 알림 API",
        description="Flutter 앱에서 사용할 수 있는 헬스장 출석률 알림 시스템 API",
        version="1.0.0"
    )

    # CORS 설정 (Flutter 웹앱에서 요청 가능하도록)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 실제 배포 시에는 특정 도메인으로 제한하세요
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # UTF-8 응답 설정을 위한 미들웨어 추가
    @app.middleware("http")
    async def add_charset_middleware(request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type") == "application/json":
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response

    @app.get("/")
    def read_root():
        return {"message": "헬스장 출석률 알림 API 서버가 실행 중입니다. (출석률: 지난 7일간 데이터 기준)"}

    @app.get("/api/user-list", response_model=UserListResponse)
    def get_user_list():
        """
        사용 가능한 사용자 ID 목록을 반환하는 API
        
        Returns:
            사용 가능한 사용자 ID 목록
        """
        try:
            # 회원 ID 조회
            user_ids = get_all_user_ids.invoke("")
            
            if not user_ids:
                return UserListResponse(
                    success=False,
                    user_ids=[],
                    message="사용자 목록을 찾을 수 없습니다."
                )
                
            return UserListResponse(
                success=True,
                user_ids=user_ids,
                message="사용 가능한 사용자 ID 목록입니다."
            )
            
        except Exception as e:
            logger.error(f"사용자 목록 가져오기 오류: {str(e)}")
            return UserListResponse(
                success=False,
                user_ids=[],
                message=f"사용자 목록을 가져오는 중 오류가 발생했습니다: {str(e)}"
            )

    @app.get("/api/test-user/{user_id}", response_model=UserResponse)
    def test_user_data(user_id: str):
        """
        테스트용 API - 특정 사용자의 데이터 확인
        
        Args:
            user_id: 사용자 ID
        
        Returns:
            사용자 데이터 또는 오류 메시지
        """
        logger.info(f"테스트 API: 사용자 {user_id} 데이터 조회 요청, 타입={type(user_id)}")
        
        try:
            # 회원 데이터 조회 (invoke 메서드 사용)
            user_data = get_user_data.invoke(user_id)
            
            # 에러 확인
            if "error" in user_data:
                return UserResponse(
                    success=False,
                    user_id=user_id,
                    error=user_data["error"]
                )
                
            # 데이터 변환
            return UserResponse(
                success=True,
                user_id=str(user_data["id"]),
                user_name=user_data["name"],
                email=user_data["email"],
                fcm_token=user_data.get("fcm_token"),
                personal_goal=user_data.get("personal_goal"),
                attendance_rate=user_data.get("attendance_rate")
            )
            
        except Exception as e:
            logger.error(f"사용자 데이터 조회 중 오류: {str(e)}")
            return UserResponse(
                success=False,
                user_id=user_id,
                error=f"사용자 데이터 조회 중 오류: {str(e)}"
            )

    @app.get("/api/notification/user/{user_id}", response_model=NotificationResponse)
    async def get_user_notification(user_id: str, fcm_token: str = None):
        """
        특정 사용자에 대한 알림 메시지 생성 및 반환 API
        
        Args:
            user_id: 사용자 ID
            fcm_token: Firebase Cloud Messaging 토큰 (선택 사항)
            
        Returns:
            알림 메시지 정보
        """
        try:
            logger.info(f"알림 요청 받음 - 사용자 ID: {user_id}, FCM 토큰 제공 여부: {fcm_token is not None}")
            
            # 회원 데이터 조회 (invoke 메서드 사용)
            user_data = get_user_data.invoke(user_id)
            if "error" in user_data:
                return NotificationResponse(
                    success=False,
                    user_id=user_id,
                    error=user_data["error"]
                )
            
            logger.info(f"사용자 데이터: {user_data}")
            
            # 알림 처리
            result = process_user_notification(user_id)
            
            if "error" in result:
                return NotificationResponse(
                    success=False,
                    user_id=user_id,
                    error=result["error"]
                )
            
            # FCM 토큰이 제공된 경우 사용자 데이터에 추가
            if fcm_token:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE member SET fcm_token = %s WHERE id = %s",
                        (fcm_token, int(user_id) if user_id.isdigit() else user_id)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                    logger.info(f"사용자 {user_id}의 FCM 토큰이 업데이트되었습니다.")
                except Exception as e:
                    logger.error(f"FCM 토큰 업데이트 중 오류: {str(e)}")
                
            # 응답 생성
            return NotificationResponse(
                success=True,
                user_id=user_id,
                user_name=user_data.get("name"),
                message=result.get("message", ""),
                personal_goal=user_data.get("personal_goal"),
                attendance_rate=user_data.get("attendance_rate"),
                notification_sent=result.get("notification_sent", False)
            )
            
        except Exception as e:
            logger.error(f"알림 처리 중 예외 발생: {str(e)}")
            return NotificationResponse(
                success=False,
                user_id=user_id,
                error=f"알림 처리 중 오류 발생: {str(e)}"
            )

    @app.get("/api/notification/all", response_model=AllNotificationsResponse)
    def get_all_notifications(fcm_token: str = None):
        """
        모든 사용자에 대한 알림 메시지 생성 및 반환 API
        
        Args:
            fcm_token: Firebase Cloud Messaging 토큰 (선택 사항)
        
        Returns:
            모든 사용자의 알림 메시지 정보
        """
        try:
            logger.info(f"API 요청: 모든 회원에 대한 알림 요청 (FCM 토큰 제공: {fcm_token is not None})")
            
            # FCM 토큰이 제공된 경우 모든 사용자에게 업데이트
            if fcm_token:
                try:
                    user_ids = get_all_user_ids.invoke("")
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    for user_id in user_ids:
                        cursor.execute(
                            "UPDATE member SET fcm_token = %s WHERE id = %s",
                            (fcm_token, int(user_id) if isinstance(user_id, str) and user_id.isdigit() else user_id)
                        )
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    logger.info(f"모든 사용자의 FCM 토큰이 업데이트되었습니다.")
                except Exception as e:
                    logger.error(f"FCM 토큰 업데이트 중 오류: {str(e)}")
            
            # 모든 회원 처리
            results = process_all_users()
            
            if "error" in results:
                return AllNotificationsResponse(
                    success=False,
                    total_count=0,
                    notifications=[],
                    error=results["error"]
                )
                
            # 회원별 결과 변환
            notifications = []
            for user_id, result in results.items():
                if "error" in result:
                    continue
                    
                try:
                    # 회원 데이터 조회 (알림에 필요한 추가 데이터)
                    user_data = get_user_data.invoke(user_id)
                    
                    notifications.append(
                        NotificationItem(
                            user_id=str(user_id),
                            user_name=user_data.get("name", ""),
                            message=result.get("message", ""),
                            attendance_rate=user_data.get("attendance_rate", 0.0),
                            notification_sent=result.get("notification_sent", False)
                        )
                    )
                except Exception as e:
                    logger.error(f"회원 {user_id} 처리 결과 변환 중 오류: {str(e)}")
            
            # 디버그 로그 추가
            total_count = len(notifications)
            logger.info(f"생성된 알림 개수: {total_count}")
            
            return AllNotificationsResponse(
                success=True,
                total_count=total_count,
                notifications=notifications
            )
                
        except Exception as e:
            # 기타 예외는 500 에러로 변환
            logger.error(f"API 오류: 모든 회원 처리 중 예외 발생 - {str(e)}")
            return AllNotificationsResponse(
                success=False,
                total_count=0,
                notifications=[],
                error=f"모든 회원 처리 중 오류 발생: {str(e)}"
            )
    
    return app

def start_server(host="0.0.0.0", port=8000, reload=False):
    """서버를 시작하는 함수"""
    app = create_app()
    logger.info(f"API 서버 시작 - http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=reload)

if __name__ == "__main__":
    start_server() 