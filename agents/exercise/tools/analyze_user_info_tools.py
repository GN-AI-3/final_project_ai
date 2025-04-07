from typing import Dict, List
from langchain.tools import tool
from pydantic import BaseModel, Field
from ..models.state_models import WorkoutState
from langchain_core.messages import AIMessage

class AnalysisInput(BaseModel):
    exercise_history: str = Field(..., description="운동 경력 (예: '1년', '6개월')")
    age: int = Field(..., description="나이")
    weight: float = Field(..., description="체중(kg)")
    height: float = Field(..., description="키(cm)")
    injuries: List[str] = Field(..., description="부상/제한사항 목록")
    goals: List[str] = Field(..., description="운동 목표 목록")
    available_equipment: List[str] = Field(..., description="사용 가능한 운동 장비 목록")
    preferred_workout_time: str = Field(..., description="선호하는 운동 시간")
    weekly_workout_days: int = Field(..., description="주간 운동 일수")

@tool(args_schema=AnalysisInput)
def analyze_user_info(exercise_history: str, age: int, weight: float, height: float,
                     injuries: List[str], goals: List[str], available_equipment: List[str],
                     preferred_workout_time: str = "morning", weekly_workout_days: int = 3) -> Dict:
    """사용자의 정보를 분석하여 피트니스 레벨과 중점 영역을 결정"""
    # 운동 경력에 따른 피트니스 레벨 결정
    if "년" in exercise_history:
        years = float(exercise_history.replace("년", ""))
        fitness_level = "advanced" if years > 3 else "intermediate" if years > 1 else "beginner"
    elif "개월" in exercise_history:
        months = float(exercise_history.replace("개월", ""))
        fitness_level = "intermediate" if months > 6 else "beginner"
    else:
        fitness_level = "beginner"
    
    # 목표에 따른 중점 영역 결정
    focus_areas = []
    if "근력" in " ".join(goals):
        focus_areas.append("strength")
    if "체력" in " ".join(goals):
        focus_areas.append("endurance")
    if "체중" in " ".join(goals):
        focus_areas.append("weight_management")
    if not focus_areas:
        focus_areas = ["general_fitness"]
    
    # BMI 계산
    height_m = height / 100
    bmi = weight / (height_m * height_m)
    
    # BMI에 따른 제한사항 추가
    restrictions = injuries.copy()
    if bmi > 30:
        restrictions.append("high_impact_exercises")
    elif bmi < 18.5:
        restrictions.append("intensive_cardio")
    
    return {
        "fitness_level": fitness_level,
        "focus_areas": focus_areas,
        "restrictions": restrictions,
        "preferred_workout_time": preferred_workout_time,
        "weekly_workout_days": weekly_workout_days,
        "bmi": bmi
    } 

# @tool()
# def get_user_database(state: WorkoutState) -> WorkoutState:
#     """사용자 정보 DB에서 가져오기"""
#     # DB 연동해서 데이터 값 가져오기

#     state["messages"].append(AIMessage(content="사용자 DB 조회"))

#     return {
#         "messages": state["messages"],
#         "user_info": {
#             "user_id": state["user_info"]["user_id"],
#             "exercise_history": "1년",
#             "age": 25,
#             "weight": 70,
#             "height": 175,
#             "injuries": ["허리 통증"],
#             "goals": ["근력 향상", "체력 향상"],
#             "available_equipment": ["덤벨", "바벨", "매트"],
#             "preferred_workout_time": "아침",
#             "weekly_workout_days": 3
#         },
#         "current_step": state["current_step"],
#         "workout_plan": state["workout_plan"],
#         "feedback": state["feedback"]
#     }