from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI

class BaseAgent:
    """
    모든 에이전트의 기본 클래스
    """
    def __init__(self, model: Optional[ChatOpenAI] = None, llm: Optional[ChatOpenAI] = None):
        """
        에이전트 초기화.
        
        Args:
            model: 레거시 파라미터 이름 (llm이 없을 경우 사용)
            llm: LangChain ChatOpenAI 모델 인스턴스
        """
        # model과 llm 둘 중 하나는 제공되어야 함
        if model is None and llm is None:
            raise ValueError("model 또는 llm 중 하나는 반드시 제공되어야 합니다.")
        
        # llm이 제공되었으면, 그것을 사용
        # 그렇지 않으면 model 파라미터 사용
        self.model = llm if llm is not None else model
    
    async def process(self, message: str, email: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        메시지를 처리하고 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항)
            chat_history: 대화 내역 (선택사항)
            
        Returns:
            Dict[str, Any]: 응답 메시지와 관련 정보
        """
        raise NotImplementedError("Subclasses must implement process()") 