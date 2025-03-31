from typing import Dict, Any
from ..models.state_models import WorkoutState
from ..tools.analysis_tools import get_user_info, analyze_user_info
from langchain_core.messages import AIMessage

def analyze_user_info_node(state: WorkoutState) -> WorkoutState:
    """사용자 정보 분석 및 초기화"""
    # 사용자 정보 가져오기
    user_info = get_user_info.invoke({})
    
    # 사용자 정보 분석
    analysis_result = analyze_user_info.invoke(user_info)
    
    # 분석 결과를 상태에 추가
    state["user_info"] = analysis_result
    
    # 사용자 정보 분석 완료 메시지 추가
    state["messages"].append(AIMessage(content="사용자 정보를 분석했습니다. 맞춤형 운동 계획을 생성하겠습니다."))
    
    return state 