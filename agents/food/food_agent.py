# 📂 make2/main.py
 
from typing import ClassVar, Optional, List, Dict, Any
import logging

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from agents.food.new_agent_graph import run_super_agent

# 로깅 설정
logger = logging.getLogger(__name__)


class FoodAgent(BaseModel):
    """음식 관련 에이전트"""
    
    DEFAULT_MODEL: ClassVar[str] = "gpt-4o-mini"
    model: Optional[ChatOpenAI] = None
    
    def __init__(self, model: Optional[ChatOpenAI] = None, **data):
        """음식 에이전트 초기화"""
        super().__init__(**data)
        if model is None:
            self.model = ChatOpenAI(
                model=self.DEFAULT_MODEL,
                temperature=0.7
            )
        else:
            self.model = model
            
    async def process(self, message: str, email: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
            # 사용자 ID 설정
            user_id = int(email) if email else 4

            if email:
                logger.info(f"이메일로 사용자 조회(미구현): {email}")
                # 실제 이메일->ID 변환 코드 필요
             
            # 사용자 정보 구성
            user_info = {
                "user_id": user_id,
                "email": email,
                "chat_history": chat_history or []
            }
            
            try:
                # run_super_agent를 통해 chain 실행
                response = await run_super_agent(
                    message, 
                    member_id=user_id,
                    user_info=user_info
                )
                
                logger.info(f"응답: {response}")
                return {"type": "food", "response": response}
            except Exception as e:
                logger.error(f"에러 발생: {str(e)}")
                return {"type": "food", "response": f"죄송합니다. 오류가 발생했습니다: {str(e)}"} 