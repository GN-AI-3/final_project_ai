from typing import Any, List, Dict
from pydantic import BaseModel

class ptScheduleState(BaseModel):
    message: str
    trainer_id: int
    response: str = None
    chat_history: List[Dict[str, Any]] = []
