"""
헬스장 출석률 알림 시스템 FastAPI 서버
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
import os
from attendance_app import (
    process_user, 
    process_all_users, 
    logger, 
    get_user_data, 
    get_all_user_ids,
    get_db_connection
)
import psycopg2.extras

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

# 응답 모델 정의
class NotificationResponse(BaseModel):
    success: bool
    user_id: str
    message: Optional[str] = None
    error: Optional[str] = None

class UserData(BaseModel):
    name: str
    attendance_rate: int
    personal_goal: str

class UserResponse(BaseModel):
    success: bool
    user_id: str
    data: Optional[UserData] = None
    error: Optional[str] = None

class UserListResponse(BaseModel):
    success: bool
    user_ids: List[str]
    message: Optional[str] = None

class AllNotificationsResponse(BaseModel):
    success: bool
    notifications: Dict[str, Any]
    total_count: Optional[int] = None
    error: Optional[str] = None

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
        # 데이터베이스 연결 확인
        conn = get_db_connection()
        if not conn:
            return UserListResponse(
                success=False,
                user_ids=[],
                message="데이터베이스 연결에 실패했습니다."
            )
            
        try:
            with conn.cursor() as cursor:
                # member 테이블에서 모든 사용자 ID 조회
                cursor.execute("SELECT id FROM member WHERE role = 'member'")
                # 반드시 ID를 문자열로 변환
                user_ids = [str(row[0]) for row in cursor.fetchall()]
                logger.info(f"DB에서 가져온 사용자 ID 목록: {user_ids}")
                
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
            logger.error(f"사용자 목록 조회 중 오류: {str(e)}")
            return UserListResponse(
                success=False,
                user_ids=[],
                message=f"사용자 목록을 가져오는 중 오류가 발생했습니다: {str(e)}"
            )
        finally:
            conn.close()
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
    
    # ID가 숫자인 경우 변환 처리
    original_id = user_id
    try:
        if user_id.isdigit():
            user_id = int(user_id)
            logger.info(f"숫자 ID 변환: {user_id}, 타입={type(user_id)}")
    except Exception as e:
        logger.error(f"ID 변환 중 오류: {str(e)}")
    
    # 데이터베이스 직접 연결하여 데이터 조회
    conn = get_db_connection()
    if not conn:
        logger.error("데이터베이스 연결을 만들 수 없습니다.")
        return UserResponse(
            success=False,
            user_id=str(original_id),
            error="데이터베이스 연결에 실패했습니다."
        )
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 먼저 사용자가 존재하는지 확인
            cursor.execute("SELECT EXISTS(SELECT 1 FROM member WHERE id = %s)", (user_id,))
            exists = cursor.fetchone()[0]
            logger.info(f"데이터베이스에 사용자 {user_id} 존재 여부: {exists}")
            
            if not exists:
                return UserResponse(
                    success=False,
                    user_id=str(original_id),
                    error=f"사용자 ID '{original_id}'에 대한 데이터를 찾을 수 없습니다."
                )
            
            # 사용자 정보 조회
            cursor.execute("""
                SELECT id, name, email, fcm_token, role, goal
                FROM member
                WHERE id = %s
            """, (user_id,))
            
            user_record = cursor.fetchone()
            
            if not user_record:
                logger.error(f"사용자 {user_id} 정보를 조회할 수 없습니다.")
                return UserResponse(
                    success=False,
                    user_id=str(original_id),
                    error=f"사용자 ID '{original_id}'에 대한 데이터를 찾을 수 없습니다."
                )
            
            logger.info(f"사용자 레코드 발견: {dict(user_record)}")
            
            # 스케줄 확인
            cursor.execute(
                "SELECT COUNT(*) FROM member_schedule WHERE member_id = %s AND is_active = true",
                (user_id,)
            )
            schedule_count = cursor.fetchone()[0]
            logger.info(f"활성화된 스케줄 수: {schedule_count}")
            
            # 출석률 계산
            if schedule_count > 0:
                # 스케줄 기반 출석률 계산
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
                """, (user_id, user_id))
            else:
                # 일반 출석률 계산
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM attendance 
                    WHERE member_id = %s 
                    AND attendance_date >= current_date - INTERVAL '7 days'
                    AND status = '출석'
                """, (user_id,))
            
            attendance_result = cursor.fetchone()
            logger.info(f"출석률 계산 결과: {dict(attendance_result) if attendance_result else None}")
            
            if schedule_count > 0:
                attended_count = attendance_result["attended_count"] if attendance_result else 0
                total_scheduled = max(1, attendance_result["total_scheduled"] if attendance_result else 7)
            else:
                attended_count = attendance_result["count"] if attendance_result else 0
                total_scheduled = 7
            
            # 출석률 계산
            attendance_rate = min(100, int((attended_count * 100) / total_scheduled))
            logger.info(f"출석률 계산: {attended_count}/{total_scheduled} = {attendance_rate}%")
            
            # 응답 생성
            return UserResponse(
                success=True,
                user_id=str(original_id),
                data=UserData(
                    name=user_record["name"],
                    attendance_rate=attendance_rate,
                    personal_goal=user_record["goal"]
                )
            )
            
    except Exception as e:
        logger.error(f"사용자 데이터 조회 중 오류: {str(e)}")
        return UserResponse(
            success=False,
            user_id=str(original_id),
            error=f"사용자 데이터 조회 중 오류: {str(e)}"
        )
    finally:
        conn.close()

@app.get("/api/notification/user/{user_id}", response_model=NotificationResponse)
async def get_user_notification(user_id: str, fcm_token: Optional[str] = None):
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
        
        # ID가 숫자인 경우 변환 처리
        try:
            if user_id.isdigit():
                user_id = int(user_id)
                logger.info(f"숫자 ID 변환: {user_id}")
        except:
            pass
        
        # 사용자 데이터 확인
        user_data = get_user_data(user_id)
        if not user_data:
            logger.error(f"사용자 데이터를 찾을 수 없음: {user_id}")
            raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {user_id}")
        
        logger.info(f"사용자 데이터: {user_data}")
        
        # 테스트 FCM 토큰 사용 (선택 사항)
        test_fcm_token = os.getenv("TEST_FCM_TOKEN")
        if not fcm_token and test_fcm_token:
            fcm_token = test_fcm_token
            logger.info("환경 변수에서 테스트 FCM 토큰을 사용합니다.")
        
        # 알림 처리 (process_user 함수 호출)
        try:
            logger.info(f"process_user 함수 호출 시작: user_id={user_id}")
            # FCM 토큰을 함께 전달
            message = process_user(user_id, fcm_token=fcm_token)
            logger.info(f"process_user 함수 호출 완료: message={message is not None}")
            
            if message:
                logger.info(f"생성된 알림 메시지: {message[:50]}...")
                
                # 사용자 이름을 message 앞에 추가 (이름은 한 번만 포함)
                name = user_data.get("name", "")
                final_message = f"{name}님, {message}" if not message.startswith(f"{name}") else message
                
                response_data = NotificationResponse(
                    success=True,
                    user_id=str(user_id),
                    message=final_message
                )
                logger.info("알림 메시지 응답 생성 완료")
                return response_data
            else:
                logger.warning("알림 메시지가 생성되지 않았습니다")
                raise HTTPException(status_code=500, detail="알림 메시지를 생성할 수 없습니다.")
                
        except Exception as e:
            logger.error(f"알림 메시지 생성 중 오류: {str(e)}")
            raise HTTPException(status_code=500, detail=f"알림 메시지를 생성할 수 없습니다: {str(e)}")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"알림 생성 중 예상치 못한 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"알림 생성 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/notification/all", response_model=AllNotificationsResponse)
def get_all_notifications(fcm_token: Optional[str] = None):
    """
    모든 사용자에 대한 알림 메시지 생성 및 반환 API
    
    Args:
        fcm_token: Firebase Cloud Messaging 토큰 (선택 사항)
    
    Returns:
        모든 사용자의 알림 메시지 정보
    """
    try:
        logger.info(f"API 요청: 모든 회원에 대한 알림 요청 (FCM 토큰 제공: {fcm_token is not None})")
        
        try:
            # 알림 처리
            results = process_all_users()
            
            if isinstance(results, dict) and "error" in results:
                logger.error(f"알림 처리 중 오류 발생: {results['error']}")
                raise HTTPException(
                    status_code=500,
                    detail=f"알림 처리 중 오류 발생: {results['error']}"
                )
                
        except Exception as process_error:
            logger.error(f"알림 처리 중 오류 발생: {str(process_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"알림 처리 중 오류 발생: {str(process_error)}"
            )
        
        # 디버그 로그 추가
        total_count = len(results)
        logger.info(f"생성된 알림 개수: {total_count}")
        
        return AllNotificationsResponse(
            success=True,
            total_count=total_count,
            notifications=results
        )
            
    except HTTPException as http_ex:
        # 이미 생성된 HTTPException은 그대로 전달
        logger.error(f"HTTP 예외: {str(http_ex.detail)}")
        raise
    except Exception as e:
        # 기타 예외는 500 에러로 변환
        logger.error(f"API 오류: 모든 회원 처리 중 예외 발생 - {str(e)}")
        raise HTTPException(status_code=500, detail=f"모든 회원 처리 중 오류 발생: {str(e)}")

# 직접 실행 시 서버 구동
if __name__ == "__main__":
    # 데이터베이스 연결 테스트
    try:
        connection = get_db_connection()
        if connection:
            logger.info("데이터베이스 연결 테스트 성공")
            connection.close()
        else:
            logger.warning("데이터베이스 연결 테스트 실패")
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 중 오류: {str(e)}")
    
    # 서버 실행
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True) 