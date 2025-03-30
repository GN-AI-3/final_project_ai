"""
API 응답 모델 정의
"""
from pydantic import BaseModel
from typing import List, Optional

class NotificationResponse(BaseModel):
    """특정 사용자에 대한 알림 응답 모델"""
    success: bool
    user_id: str
    message: Optional[str] = None
    error: Optional[str] = None
    user_name: Optional[str] = None
    personal_goal: Optional[str] = None
    attendance_rate: Optional[float] = None
    notification_sent: Optional[bool] = None

class UserResponse(BaseModel):
    """사용자 정보 응답 모델"""
    success: bool
    user_id: str
    user_name: Optional[str] = None
    email: Optional[str] = None
    fcm_token: Optional[str] = None
    personal_goal: Optional[str] = None
    attendance_rate: Optional[float] = None
    error: Optional[str] = None

class UserListResponse(BaseModel):
    """사용자 목록 응답 모델"""
    success: bool
    user_ids: List[str]
    message: Optional[str] = None

class NotificationItem(BaseModel):
    """알림 항목 모델"""
    user_id: str
    user_name: str
    message: str
    attendance_rate: float
    notification_sent: bool

class AllNotificationsResponse(BaseModel):
    """모든 사용자에 대한 알림 응답 모델"""
    success: bool
    total_count: int
    notifications: List[NotificationItem]
    error: Optional[str] = None 