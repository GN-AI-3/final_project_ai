from typing import Dict, Any
from .base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate
from agents.agent_food.workflow import run_workflow
from agents.agent_exercise.main import main

class ExerciseAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        # prompt = ChatPromptTemplate.from_messages([
        #     ("system", "당신은 운동 전문가입니다. 사용자의 운동 관련 질문에 대해 전문적으로 답변해주세요."),
        #     ("user", "{message}")
        # ])
        # chain = prompt | self.model
        # response = await chain.ainvoke({"message": message})

        response = await main()
        return {"type": "exercise", "response": response.content}

class DietAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        # prompt = ChatPromptTemplate.from_messages([
        #     ("system", "당신은 영양 전문가입니다. 사용자의 식단 관련 질문에 대해 전문적으로 답변해주세요."),
        #     ("user", "{message}")
        # ])
        # chain = prompt | self.model
        # response = await chain.ainvoke({"message": message})

        response = await run_workflow(message)
        return {"type": "diet", "response": response.content}

class ScheduleAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 일정 관리 전문가입니다. 사용자의 일정 관련 질문에 대해 전문적으로 답변해주세요."),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "schedule", "response": response.content}

class GeneralAgent(BaseAgent):
    async def process(self, message: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 일반적인 대화를 나눌 수 있는 AI 어시스턴트입니다."),
            ("user", "{message}")
        ])
        chain = prompt | self.model
        response = await chain.ainvoke({"message": message})
        return {"type": "general", "response": response.content} 