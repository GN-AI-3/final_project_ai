from typing import Dict, Any, Optional
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

    async def process(self, message: str, member_id: Optional[int] = None, user_type: Optional[str] = None) -> Dict[str, Any]:
        try:
            logger.info(f"ScheduleAgent 처리 시작 - member_id: {member_id}, user_type: {user_type}")
            
            # member_id와 user_type을 포함한 메시지 생성
            enhanced_message = {
                "text": message,
                "member_id": member_id,
                "user_type": user_type
            }
            
            # json 문자열로 변환
            json_message = json.dumps(enhanced_message, ensure_ascii=False)
            
            # 세션 ID 생성 (member_id가 있으면 해당 값 사용)
            session_id = str(member_id) if member_id else "default"
            
            logger.info(f"ScheduleChatbot 호출 - session_id: {session_id}")
            raw_result = self.chatbot.process_message(json_message, session_id=session_id)

            # json.loads로 파싱
            parsed = json.loads(raw_result)

            return {
                "type": "schedule",
                "response": parsed.get("message", "응답이 없습니다."),
                "success": parsed.get("success", False)
            }
        except Exception as e:
            logger.error(f"ScheduleAgent 처리 오류: {str(e)}")
            return {
                "type": "schedule",
                "response": str(e),
                "success": False
            }
