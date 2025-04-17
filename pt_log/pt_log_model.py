from typing import Any, List, Dict
from pydantic import BaseModel

class ptLogState(BaseModel):
    message: str
    ptScheduleId: int
    response: str = None
    chat_history: List[Dict[str, Any]] = []
