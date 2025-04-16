"""
에이전트 실행 모듈
Supervisor에서 분류된 카테고리에 따라 적절한 에이전트를 호출하고 결과를 처리하는 기능을 제공합니다.
"""

import logging
from typing import Any, Dict, List, Optional

# 로거 설정
logger = logging.getLogger(__name__)

# 전역 변수로 agents 선언
agents = {}

def register_agent(agent_type: str, agent_instance: Any) -> None:
    """
    에이전트를 전역 레지스트리에 등록합니다.
    
    Args:
        agent_type: 에이전트 타입 (exercise, food, schedule, motivation, general 등)
        agent_instance: 에이전트 인스턴스 (process 메서드를 가지고 있어야 함)
    """
    global agents
    agents[agent_type] = agent_instance
    logger.info(f"에이전트 '{agent_type}' 등록 완료")

# 디버깅 목적의 함수들
def get_registered_agents() -> List[str]:
    """
    등록된 모든 에이전트 목록을 반환합니다. 디버깅 용도로 사용됩니다.
    
    Returns:
        List[str]: 등록된 에이전트 타입 목록
    """
    return list(agents.keys())

def get_agent_info(agent_type: str) -> Optional[Dict[str, Any]]:
    """
    특정 에이전트의 정보를 반환합니다. 디버깅 용도로 사용됩니다.
    
    Args:
        agent_type: 에이전트 타입
        
    Returns:
        Optional[Dict[str, Any]]: 에이전트 정보 딕셔너리 또는 None (등록되지 않은 경우)
    """
    if agent_type not in agents:
        return None
        
    agent = agents[agent_type]
    return {
        "type": agent_type,
        "class": agent.__class__.__name__,
        "module": agent.__class__.__module__,
        "methods": [method for method in dir(agent) if callable(getattr(agent, method)) and not method.startswith("_")]
    } 