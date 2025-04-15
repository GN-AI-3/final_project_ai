from typing import Any
from pydantic import BaseModel
from typing import Optional, List

class RoutingState(BaseModel):
    member_id: int = None
    trainer_id: int = None
    user_type: str = "member"
    message: str
    plan: Optional[str] = None
    context: Optional[List[Any]] = None
    feedback: Optional[str] = None
    result: Optional[Any] = None