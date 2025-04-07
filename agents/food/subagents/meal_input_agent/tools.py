from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate
from .analyze import MealInputAgent

class MealInputTool(BaseModel):
    """식단 입력 도구"""
    model_config = ConfigDict(validate_by_name=True)
    name: str = "meal_input"
    description: str = "식단 입력 및 조회를 처리하는 도구"
    agent: MealInputAgent = Field(default_factory=lambda: MealInputAgent())
    prompt: ChatPromptTemplate = Field(default_factory=lambda: ChatPromptTemplate.from_messages([
        ("system", "식단 입력 및 조회를 처리하는 AI 어시스턴트입니다."),
        ("human", "{input}")
    ]))

    async def process(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """식단 입력 처리"""
        try:
            return await self.agent.process(user_input, user_id)
        except Exception as e:
            print(f"식단 입력 도구 처리 중 오류 발생: {e}")
            return {
                "type": "food",
                "response": "죄송합니다. 식단 입력 처리 중 오류가 발생했습니다."
            }

def get_meal_input_tool(model_name: str = "gpt-4-turbo-preview") -> MealInputTool:
    """식단 입력 도구 생성"""
    return MealInputTool(agent=MealInputAgent(model_name)) 