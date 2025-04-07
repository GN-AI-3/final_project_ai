from typing import Dict, Any

from ..base_agent import BaseAgent
from agents.schedule.config.prompts import get_schedule_agent_prompt


class ScheduleAgent(BaseAgent):
    """스케줄 예약 에이전트 클래스"""
    
    async def process(self, message: str) -> Dict[str, Any]:
        """사용자 메시지 처리
        
        Args:
            message: 사용자 메시지
            
        Returns:
            처리 결과 딕셔너리
        """
        prompt = get_schedule_agent_prompt()
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "schedule", "response": response.content}