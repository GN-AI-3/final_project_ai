from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

class UserState(BaseModel):
    """사용자 상태를 관리하는 클래스"""
    user_id: int
    user_info: Dict[str, Any] = {}
    food_info: Dict[str, Any] = {}
    meal_records: List[Dict[str, Any]] = []
    diet_plan: Dict[str, Any] = {}
    preferences: Dict[str, Any] = {}
    deficient_nutrients: List[str] = []
    recommended_foods: List[Dict[str, Any]] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        arbitrary_types_allowed = True 