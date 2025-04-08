from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum, auto

class IntentType(Enum):
    """의도 타입"""
    MEAL_INPUT = auto()
    MEAL_RECOMMENDATION = auto()
    NUTRIENT_ANALYSIS = auto()
    MEAL_LOOKUP = auto()
    OTHER = auto()

class AgentState(BaseModel):
    """에이전트 상태"""
    user_id: str = Field(default="")
    user_input: str = Field(default="")
    intent: Optional[str] = Field(default=None)
    intent_details: Dict[str, Any] = Field(default_factory=dict)
    meal_type: str = Field(default="")
    food_input: str = Field(default="")
    meal_items: List[Dict[str, Any]] = Field(default_factory=list)
    total_nutrition: Dict[str, float] = Field(default_factory=dict)
    nutrition_analysis: Dict[str, Any] = Field(default_factory=dict)
    food_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    user_info: Optional[Dict[str, Any]] = Field(default=None)
    user_preferences: Optional[Dict[str, Any]] = Field(default=None)
    weekly_meals: List[Dict[str, Any]] = Field(default_factory=list)
    today_meals: List[Dict[str, Any]] = Field(default_factory=list)
    diet_plan: Optional[Dict[str, Any]] = Field(default=None)
    error: Optional[str] = Field(default=None)
    next_step: Optional[str] = Field(default=None)
    messages: List[Dict[str, str]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        validate_assignment = True 