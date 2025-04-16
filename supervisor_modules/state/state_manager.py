"""
상태 관리 모듈
Supervisor의 상태 관리 기능을 제공합니다.
"""

import time
import uuid
from typing import Dict, Any, List, Optional, Union, TypedDict

class SupervisorStateDict(TypedDict, total=False):
    """LangGraph용 Supervisor 상태 타입 정의"""
    request_id: str
    message: str
    email: Optional[str]
    chat_history: List[Dict[str, Any]]
    categories: List[str]
    selected_agents: List[str]
    agent_outputs: Dict[str, Any]
    agent_errors: Dict[str, str]
    response: str
    response_type: str
    error: Optional[str]
    metrics: Dict[str, Any]
    used_nodes: List[str]
    start_time: float
    context_info: Dict[str, str]

class SupervisorState:
    """LangGraph 워크플로우의 상태를 관리하는 클래스"""
    
    def __init__(self, 
                message: str = "", 
                email: str = None, 
                chat_history: List[Dict[str, Any]] = None,
                start_time: float = None,
                context: Dict[str, Any] = None,
                request_id: str = None):
        """
        상태 초기화
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일
            chat_history: 대화 내역
            start_time: 처리 시작 시간
            context: 추가 컨텍스트 정보
            request_id: 요청 ID (없으면 생성됨)
        """
        # 기본 정보
        self.request_id = request_id or str(uuid.uuid4())
        self.message = message
        self.email = email
        self.chat_history = chat_history or []
        self.start_time = start_time or time.time()
        
        # 라우팅 관련
        self.categories = []
        self.selected_agents = []
        
        # 에이전트 실행 관련
        self.agent_outputs = {}
        self.agent_errors = {}
        self.agent_results = []
        
        # 응답 관련
        self.response = ""
        self.response_type = "general"
        
        # 오류 관련
        self.error = None
        
        # 메트릭
        self.metrics = {}
        
        # 추가 컨텍스트 정보
        self.context = context or {}
        
        # 카테고리별 문맥 정보
        self.context_info = {}
        
        # 사용된 노드 추적
        self.used_nodes = []
    
    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> 'SupervisorState':
        """딕셔너리에서 상태 객체 생성"""
        state = cls()
        
        for key, value in state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        return state
    
    def to_dict(self) -> Dict[str, Any]:
        """상태를 딕셔너리로 변환"""
        return {
            "request_id": self.request_id,
            "message": self.message,
            "email": self.email,
            "chat_history": self.chat_history,
            "categories": self.categories,
            "selected_agents": self.selected_agents,
            "agent_outputs": self.agent_outputs,
            "agent_errors": self.agent_errors,
            "agent_results": getattr(self, "agent_results", []),
            "response": self.response,
            "response_type": self.response_type,
            "error": self.error,
            "metrics": self.metrics,
            "context": self.context,
            "context_info": getattr(self, "context_info", {}),
            "used_nodes": self.used_nodes
        }
    
    def set(self, key: str, value: Any) -> None:
        """상태 값 설정"""
        setattr(self, key, value)
        
    def get_conversation_context(self, max_messages: int = 5, max_chars: int = 200) -> str:
        """
        대화 기록을 컨텍스트 문자열로 변환
        
        Args:
            max_messages: 최대 메시지 수
            max_chars: 각 메시지의 최대 문자 수
            
        Returns:
            str: 대화 컨텍스트 문자열
        """
        if not self.chat_history:
            return ""
        
        context_parts = []
        
        # 최근 메시지부터 max_messages만큼 가져옴
        recent_messages = self.chat_history[-max_messages:] if len(self.chat_history) > max_messages else self.chat_history
        
        for msg in recent_messages:
            role = "사용자" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")
            
            # 메시지가 너무 길면 잘라냄
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
                
            context_parts.append(f"{role}: {content}")
            
        return "\n".join(context_parts) 