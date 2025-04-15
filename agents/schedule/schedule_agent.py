from typing import Dict, Any
import json
import logging

from agents.schedule.chatbot import ScheduleChatbot

from ..base_agent import BaseAgent

# 로거 설정
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduleAgent(BaseAgent):
    def __init__(self, model):
        super().__init__(model)
        self.chatbot = ScheduleChatbot()

    async def process(self, message: str) -> Dict[str, Any]:
        try:
            raw_result = self.chatbot.process_message(message, session_id="default")

            # json.loads로 파싱
            parsed = json.loads(raw_result)

            return {
                "type": "schedule",
                "response": parsed.get("message", "응답이 없습니다."),
                "success": parsed.get("success", False)
            }
        except Exception as e:
            return {
                "type": "schedule",
                "response": str(e),
                "success": False
            }