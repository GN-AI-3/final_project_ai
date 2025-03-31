from pydantic import BaseModel, Field
from typing import Dict, List

class UserInfoInput(BaseModel):
    exercise_history: str = Field(..., description="운동 경력 (예: '1년', '6개월')")
    age: int = Field(..., description="나이")
    weight: float = Field(..., description="체중(kg)")
    height: float = Field(..., description="키(cm)")
    injuries: List[str] = Field(..., description="부상/제한사항 목록")
    goals: List[str] = Field(..., description="운동 목표 목록")
    available_equipment: List[str] = Field(..., description="사용 가능한 운동 장비 목록")
    preferred_workout_time: str = Field(..., description="선호하는 운동 시간")
    weekly_workout_days: int = Field(..., description="주간 운동 일수")

class AnalysisInput(BaseModel):
    fitness_level: str
    focus_areas: List[str]
    restrictions: List[str]
    preferred_workout_time: str
    weekly_workout_days: int

class ExerciseRecommendationInput(BaseModel):
    fitness_level: str
    goals: List[str]
    age: int
    weight: float
    height: float
    injuries: List[str]
    available_equipment: List[str]
    target_muscles: str = None

class ExerciseResearchData(BaseModel):
    exercise_name: str
    research_papers: List[Dict]
    clinical_trials: List[Dict]
    meta_analysis: List[Dict] 