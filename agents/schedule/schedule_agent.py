from typing import Dict, Any
from ..base_agent import BaseAgent
from config.prompts import get_schedule_agent_prompt

class ScheduleAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        prompt = get_schedule_agent_prompt()
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "schedule", "response": response.content}