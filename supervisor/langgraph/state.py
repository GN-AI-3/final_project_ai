"""
상태 관리 클래스
LangGraph 파이프라인에서 사용되는 상태 객체 정의
"""

from typing import Dict, Optional, List, Any, TypedDict
from pydantic import BaseModel, Field

class GymGGunState(BaseModel):
    """
    GymGGun 파이프라인의 상태를 관리하는 클래스
    메시지 처리 과정의 상태와 결과를 추적
    """
    # 사용자 입력
    message: str = Field(default="")
    email: str = Field(default="")
    
    # 메시지 분류 결과
    classified_type: str = Field(default="general")
    agent_messages: Dict[str, str] = Field(default_factory=dict)  # 각 에이전트별 메시지
    all_categories: List[str] = Field(default_factory=list)  # 모든 관련 카테고리
    
    # 에이전트 결과
    agent_results: List[Dict[str, Any]] = Field(default_factory=list)  # 여러 에이전트의 처리 결과
    
    # 처리 결과
    response: Optional[str] = Field(default=None)
    response_type: str = Field(default="general")
    
    # 처리 시간 추적
    start_time: Optional[float] = Field(default=None)
    end_time: Optional[float] = Field(default=None)
    
    # 오류 정보
    error: Optional[str] = Field(default=None)
    
    # 메트릭 추적
    metrics: Dict[str, Any] = Field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        상태에서 값을 가져오는 편의 메서드
        존재하지 않는 키에 대해 기본값 반환
        """
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        상태에 값을 설정하는 편의 메서드
        """
        setattr(self, key, value)
        
    def update(self, data: Dict[str, Any]) -> None:
        """
        여러 값을 한 번에 업데이트하는 편의 메서드
        """
        for key, value in data.items():
            self.set(key, value)
            
    def to_dict(self) -> Dict[str, Any]:
        """
        상태를 딕셔너리로 변환
        """
        return self.dict() 