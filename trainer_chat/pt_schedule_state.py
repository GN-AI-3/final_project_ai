from typing import Any, List, Dict
from pydantic import BaseModel

class ptScheduleState(BaseModel):
    input: str
    trainer_id: int
    response: str | None = None
    chat_history: List[Dict[str, Any]] = []