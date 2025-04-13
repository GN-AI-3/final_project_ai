from typing import Dict, Any, List, Optional
from ..base_agent import BaseAgent
from agents.schedule.config.prompts import get_schedule_agent_prompt

class ScheduleAgent(BaseAgent):
    async def process(self, message: str, email: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 일정 관련 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항)
            chat_history: 대화 내역 (선택사항)
            
        Returns:
            Dict[str, Any]: 응답 메시지와 관련 정보
        """
        prompt = get_schedule_agent_prompt()
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "schedule", "response": response.content}