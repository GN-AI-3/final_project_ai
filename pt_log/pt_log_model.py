from typing import Any
from pydantic import BaseModel
from typing import Optional, List

class ptLogState(BaseModel):
    message: str
    ptScheduleId: int = None
    plan: str = None
