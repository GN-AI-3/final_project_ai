from typing import Any, List, Dict
from pydantic import BaseModel

class workoutLogState(BaseModel):
    message: str
    memberId: int
    date: str
    response: str = None
    chat_history: List[Dict[str, Any]] = []
