from typing import Dict, Any
from langchain_openai import ChatOpenAI

class BaseAgent:
    """
    모든 에이전트의 기본 클래스
    """
    def __init__(self, model: ChatOpenAI):
        self.model = model
    
    async def process(self, message: str) -> Dict[str, Any]:
        """
        메시지를 처리하고 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            
        Returns:
            Dict[str, Any]: 응답 메시지와 관련 정보
        """
        raise NotImplementedError("Subclasses must implement process()") 