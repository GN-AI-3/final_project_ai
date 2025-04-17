from typing import Any
from pydantic import BaseModel

class ptLogState(BaseModel):
    message: str
    ptScheduleId: int
    response: str = None
