from typing import Dict, Any, List, Optional
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate
from common_prompts.prompts import AGENT_CONTEXT_PROMPT

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
        # 대화 내역 포맷팅
        formatted_history = ""
        if chat_history and len(chat_history) > 0:
            # 최대 5개의 최신 메시지만 사용
            recent_history = chat_history[-5:]
            for entry in recent_history:
                role = "사용자" if entry.get("role", "") == "user" else "AI"
                content = entry.get("content", "")
                formatted_history += f"{role}: {content}\n"
        
        # 대화 내역이 있는 경우 AGENT_CONTEXT_PROMPT 사용
        if formatted_history:
            system_prompt = AGENT_CONTEXT_PROMPT
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", message)
            ])
            
            # 프롬프트에 필요한 변수 설정
            variables = {
                "message": message,
                "chat_history": formatted_history
            }
        else:
            # 대화 내역이 없는 경우 간단한 프롬프트 사용
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 일반적인 대화를 나눌 수 있는 AI 어시스턴트입니다."),
                ("human", "{message}")
            ])
            variables = {"message": message}
            
        chain = prompt | self.model
        response = await chain.ainvoke(variables)
        return {"type": "general", "response": response.content} 