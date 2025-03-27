"""
헬스장 출석률 알림 에이전트 워크플로우 정의
"""
import logging
from typing import Dict, List, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END

from .nodes import (
    get_user_data,
    analyze_attendance,
    create_notification,
    deliver_notification
)

logger = logging.getLogger(__name__)

class AttendanceState(TypedDict):
    """워크플로우 상태를 정의하는 타입"""
    user_id: str
    user_found: bool
    user_data: Dict
    attendance_status: str
    message_type: str
    send_notification: bool
    notifications: List[str]
    delivery_results: List[Dict]

def should_send_notification(state: AttendanceState) -> Literal["send_notification", "end"]:
    """
    알림 전송 여부를 결정하는 라우터 함수
    """
    if state.get("send_notification", False):
        return "send_notification"
    else:
        return "end"

def create_attendance_workflow() -> StateGraph:
    """
    헬스장 출석률 알림 워크플로우 생성
    """
    # 워크플로우 상태 그래프 생성
    workflow = StateGraph(AttendanceState)
    
    # 노드 추가
    workflow.add_node("get_user_data", get_user_data)
    workflow.add_node("analyze_attendance", analyze_attendance)
    workflow.add_node("create_notification", create_notification)
    workflow.add_node("deliver_notification", deliver_notification)
    
    # 엣지 정의 (노드 간 연결)
    workflow.add_edge("get_user_data", "analyze_attendance")
    workflow.add_conditional_edges(
        "analyze_attendance",
        should_send_notification,
        {
            "send_notification": "create_notification",
            "end": END
        }
    )
    workflow.add_edge("create_notification", "deliver_notification")
    workflow.add_edge("deliver_notification", END)
    
    # 시작 노드 설정
    workflow.set_entry_point("get_user_data")
    
    logger.info("헬스장 출석률 알림 워크플로우 생성 완료")
    
    return workflow 