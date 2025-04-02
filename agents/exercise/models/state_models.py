from typing import TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class WorkoutState(TypedDict):
    messages: List[BaseMessage]
    user_info: Dict[str, Any]
    current_step: str
    workout_plan: Dict[str, Any]
    feedback: Dict[str, Any] 

    # initial_state: WorkoutState = {
    #     "messages": [{"type": "human", "content": message}],  # HumanMessage 객체 대신 딕셔너리 사용
    #     "user_info": {
    #         "exercise_history": "1년",
    #         "age": 25,
    #         "weight": 70,
    #         "height": 175,
    #         "injuries": ["허리 통증"],
    #         "goals": ["근력 향상", "체력 향상"],
    #         "available_equipment": ["덤벨", "바벨", "매트"],
    #         "preferred_workout_time": "아침",
    #         "weekly_workout_days": 3
    #     },
    #     "current_step": "start",
    #     "workout_plan": {},
    #     "feedback": {}
    # }

class RoutingState(TypedDict):
    message: str
    llm: ChatOpenAI = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )
    category: str = "exercise"
