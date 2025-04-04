from typing import Dict, Any
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate

class FoodAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 영양 전문가입니다. 사용자의 식단 관련 질문에 대해 전문적으로 답변해주세요."),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "food", "response": response.content} 