from typing import Any
from pydantic import BaseModel

class workoutLogState(BaseModel):
    message: str
    memberId: int
    date: str
    result: str = None
