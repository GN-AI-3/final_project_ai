"""
API 응답 모델 정의
"""
from pydantic import BaseModel, Field
from typing import List, Optional

class NotificationResponse(BaseModel):
    """
    알림 메시지 생성 응답 모델
    """
    success: bool = Field(description="성공 여부")
    user_id: str = Field(description="회원 ID (이메일)")
    user_name: Optional[str] = Field(None, description="회원 이름")
    message: Optional[str] = Field(None, description="생성된 알림 메시지")
    personal_goal: Optional[str] = Field(None, description="개인 목표")
    attendance_rate: Optional[float] = Field(None, description="지난 7일간 출석률")
    notification_sent: Optional[bool] = Field(None, description="푸시 알림 전송 여부")
    error: Optional[str] = Field(None, description="오류 메시지 (실패 시)")

class UserResponse(BaseModel):
    """
    회원 데이터 응답 모델
    """
    success: bool = Field(description="성공 여부")
    user_id: str = Field(description="회원 ID (이메일)")
    user_name: Optional[str] = Field(None, description="회원 이름")
    email: Optional[str] = Field(None, description="회원 이메일")
    fcm_token: Optional[str] = Field(None, description="Firebase 클라우드 메시징 토큰")
    personal_goal: Optional[str] = Field(None, description="개인 목표")
    attendance_rate: Optional[float] = Field(None, description="지난 7일간 출석률")
    error: Optional[str] = Field(None, description="오류 메시지 (실패 시)")

class UserListResponse(BaseModel):
    """사용자 목록 응답 모델"""
    success: bool
    user_ids: List[str]
    message: Optional[str] = None

class NotificationItem(BaseModel):
    """
    알림 메시지 항목 모델
    """
    user_id: str = Field(description="회원 ID (이메일)")
    user_name: Optional[str] = Field(None, description="회원 이름")
    message: Optional[str] = Field(None, description="생성된 알림 메시지")
    notification_sent: Optional[bool] = Field(None, description="푸시 알림 전송 여부")
    error: Optional[str] = Field(None, description="오류 메시지 (실패 시)")

class AllNotificationsResponse(BaseModel):
    """
    모든 회원 알림 메시지 생성 응답 모델
    """
    success: bool = Field(description="성공 여부")
    notifications: List[NotificationItem] = Field(description="알림 메시지 목록")
    error: Optional[str] = Field(None, description="오류 메시지 (실패 시)") 