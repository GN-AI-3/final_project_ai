from typing import TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage

class WorkoutState(TypedDict):
    messages: List[BaseMessage]
    user_info: Dict[str, Any]
    current_step: str
    workout_plan: Dict[str, Any]
    feedback: Dict[str, Any] 