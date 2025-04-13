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
        # 대화 내역 포맷팅
        formatted_history = ""
        if chat_history and len(chat_history) > 0:
            # 최대 5개의 최신 메시지만 사용
            recent_history = chat_history[-5:]
            for entry in recent_history:
                role = "사용자" if entry.get("role", "") == "user" else "AI"
                content = entry.get("content", "")
                formatted_history += f"{role}: {content}\n"
        
        # 대화 내역이 있는 경우와 없는 경우에 따라 다른 프롬프트 사용
        if formatted_history:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 사용자와 일상 대화를 나누는 AI 어시스턴트입니다. 
이전 대화 내용을 참고하여 사용자의 질문에 적절히 답변하세요.
특히 사용자가 이전에 언급한 내용(옷, 음식, 활동 등)을 기억하고 참조해야 합니다.
사용자가 이전 대화 내용에 대해 물어본다면 정확하게 답변해 주세요."""),
                ("human", f"""이전 대화 내역:
{formatted_history}

현재 질문: {message}""")
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 일반적인 대화를 나눌 수 있는 AI 어시스턴트입니다."),
                ("human", "{message}")
            ])
            
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "general", "response": response.content} 