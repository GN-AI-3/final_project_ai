from typing import Dict, Any, List, Optional
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate

class GeneralAgent(BaseAgent):
    async def process(self, message: str, email: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 일반적인 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항)
            chat_history: 대화 내역 (선택사항)
            
        Returns:
            Dict[str, Any]: 응답 메시지와 관련 정보
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 일반적인 대화를 나눌 수 있는 AI 어시스턴트입니다."),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "general", "response": response.content} 