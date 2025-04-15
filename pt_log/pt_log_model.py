from typing import Any
from pydantic import BaseModel

class ptLogState(BaseModel):
    message: str
    ptScheduleId: int = 309
    plan: str = None
