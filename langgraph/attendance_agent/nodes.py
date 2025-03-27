"""
헬스장 출석률 기반 알림 에이전트의 노드 구현
"""
import logging
from typing import Dict, List, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .prompts import get_praise_prompt, get_encouragement_prompt, get_motivation_prompt

logger = logging.getLogger(__name__)

# 가상의 데이터베이스 역할을 하는 샘플 데이터
SAMPLE_USERS = {
    "user1": {
        "name": "김영희",
        "attendance_rate": 90,  # 90% 출석률
        "personal_goal": "체중 감량",
        "email": "user1@example.com"
    },
    "user2": {
        "name": "이철수",
        "attendance_rate": 60,  # 60% 출석률
        "personal_goal": "체형 관리",
        "email": "user2@example.com"
    },
    "user3": {
        "name": "박지민",
        "attendance_rate": 30,  # 30% 출석률
        "personal_goal": "신체 능력 강화",
        "email": "user3@example.com"
    },
    "user4": {
        "name": "최민수",
        "attendance_rate": 85,  # 85% 출석률
        "personal_goal": "건강 유지",
        "email": "user4@example.com"
    },
    "user5": {
        "name": "정수연",
        "attendance_rate": 55,  # 55% 출석률
        "personal_goal": "정신적 건강 관리",
        "email": "user5@example.com"
    },
    "user6": {
        "name": "강준호",
        "attendance_rate": 25,  # 25% 출석률
        "personal_goal": "취미",
        "email": "user6@example.com"
    }
}

def get_user_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 데이터를 가져오는 노드
    """
    user_id = state["user_id"]
    logger.info(f"헬스장 회원 {user_id}의 데이터를 가져오는 중...")
    
    # 샘플 데이터베이스에서 사용자 정보 조회
    user_data = SAMPLE_USERS.get(user_id)
    
    if not user_data:
        logger.warning(f"헬스장 회원 {user_id}를 찾을 수 없습니다.")
        return {
            "user_id": user_id,
            "user_found": False
        }
    
    logger.info(f"헬스장 회원 {user_id} 데이터 조회 완료: 출석률 {user_data['attendance_rate']}%")
    
    return {
        "user_id": user_id,
        "user_found": True,
        "user_data": user_data
    }

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
    elif attendance_rate >= 50:
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
    llm = ChatOpenAI(temperature=0.7)
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