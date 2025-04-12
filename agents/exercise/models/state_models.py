from typing import Any
from pydantic import BaseModel
from typing import Optional, List

class RoutingState(BaseModel):
    user_id: str = "1"
    message: str
    plan: Optional[str] = None
    context: Optional[List[Any]] = None
    feedback: Optional[str] = None
    result: Optional[Any] = None