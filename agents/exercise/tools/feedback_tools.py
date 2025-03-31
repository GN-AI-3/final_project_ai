from typing import Dict
from langchain.tools import tool

@tool
def adjust_plan_based_on_feedback(workout_plan: Dict, feedback: Dict) -> Dict:
    """사용자 피드백을 바탕으로 운동 계획 조정"""
    adjusted_plan = workout_plan.copy()
    
    if feedback.get("too_difficult"):
        # 운동 강도 감소
        adjusted_plan["intensity"]["sets"] -= 1
        adjusted_plan["intensity"]["reps"] = "12-15"
        adjusted_plan["intensity"]["rest"] = "90-120초"
        if "cardio_duration" in adjusted_plan["intensity"]:
            adjusted_plan["intensity"]["cardio_duration"] = "15-20분"
    
    if feedback.get("too_easy"):
        # 운동 강도 증가
        adjusted_plan["intensity"]["sets"] += 1
        adjusted_plan["intensity"]["reps"] = "6-10"
        adjusted_plan["intensity"]["rest"] = "30-45초"
        if "cardio_duration" in adjusted_plan["intensity"]:
            adjusted_plan["intensity"]["cardio_duration"] = "40-50분"
    
    return adjusted_plan 