from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent

class Supervisor:
    def __init__(self, model: ChatOpenAI):
        self.model = model
        self.agents = {
            "exercise": ExerciseAgent(model),
            "food": FoodAgent(model),
            "schedule": ScheduleAgent(model),
            "general": GeneralAgent(model)
        }
        
    async def analyze_message(self, message: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """다음 카테고리 중 하나로 메시지를 분류해주세요:
            - exercise: 운동, 운동 방법, 운동 효과 등
            - food: 식단, 영양, 음식 등
            - schedule: 일정, 시간 관리, 계획 등
            - general: 위 카테고리에 속하지 않는 일반적인 대화
            
            응답은 위 카테고리 중 하나만 반환해주세요."""),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return response.content.strip().lower()
    
    async def process(self, message: str) -> Dict[str, Any]:
        category = await self.analyze_message(message)
        agent = self.agents.get(category, self.agents["general"])
        return await agent.process(message) 