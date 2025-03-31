from typing import Dict, Any
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate

class GeneralAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 일반적인 대화를 나눌 수 있는 AI 어시스턴트입니다."),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "general", "response": response.content} 