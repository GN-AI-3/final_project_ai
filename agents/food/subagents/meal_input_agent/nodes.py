from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from langchain.prompts import ChatPromptTemplate
from .analyze import MealInputAgent

class MealInputState(BaseModel):
    """식단 입력 상태"""
    model_config = ConfigDict(validate_by_name=True)
    user_data: Dict[str, Any]
    user_input: str
    messages: List[Dict[str, str]]
    context: Dict[str, Any]
    task: str = ""
    meal_data: Dict[str, Any] = {}

class MealInputNode:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        """식단 입력 노드 초기화"""
        self.agent = MealInputAgent(model_name)
        self.response_prompt = ChatPromptTemplate.from_messages([
            ("system", "사용자의 식단 관련 요청에 응답하는 AI 어시스턴트입니다."),
            ("human", "{input}")
        ])
    
    async def process(self, state: MealInputState) -> Dict[str, Any]:
        """식단 입력 처리"""
        try:
            # 사용자 ID 추출
            user_id = state.user_data.get("user_id")
            if not user_id:
                return {
                    "type": "food",
                    "response": "죄송합니다. 사용자 정보를 찾을 수 없습니다."
                }
            
            # 식단 입력 처리
            result = await self.agent.process(state.user_input, user_id)
            
            # 상태 업데이트
            state.messages.append({
                "role": "assistant",
                "content": result["response"]
            })
            
            return result
            
        except Exception as e:
            print(f"식단 입력 처리 중 오류 발생: {e}")
            return {
                "type": "food",
                "response": "죄송합니다. 식단 입력 처리 중 오류가 발생했습니다."
            } 