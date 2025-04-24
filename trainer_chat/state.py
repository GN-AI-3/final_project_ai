from typing import Any, Dict, List
from pydantic import BaseModel

class trainerChatState(BaseModel):
    input: str
    trainer_id: int
    response: str | None = None
    chat_history: List[Dict[str, Any]] = []