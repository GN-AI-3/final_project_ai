from typing import Dict, List
import json
from ..workflows.workout_workflow import create_workout_workflow

def is_workout_request(message: str) -> bool:
    """사용자 메시지가 운동 루틴 요청인지 확인"""
    workout_keywords = [
        "운동", "루틴", "추천", "계획", "프로그램", "트레이닝",
        "workout", "routine", "recommend", "plan", "program", "training"
    ]
    return any(keyword in message.lower() for keyword in workout_keywords)

def generate_workout_routine(user_info: Dict) -> Dict:
    """Generate a personalized workout routine based on user information."""
    app = create_workout_workflow()
    
    initial_state = {
        "messages": [],
        "user_info": user_info,
        "workout_plan": {},
        "feedback": {},
        "progress": {},
        "current_step": "start"
    }
    
    final_state = app.invoke(initial_state)
    
    # 메시지 내용 간소화
    serializable_state = {
        "messages": [
            {
                "type": msg.__class__.__name__,
                "content": msg.content,
                "additional_kwargs": {
                    k: v for k, v in msg.additional_kwargs.items() 
                    if v and not (isinstance(v, dict) and not v)
                } if hasattr(msg, "additional_kwargs") else {}
            }
            for msg in final_state["messages"]
        ],
        "workout_plan": final_state["workout_plan"],
        "current_step": final_state["current_step"]
    }
    
    return serializable_state

def chat_with_workout_agent():
    """운동 루틴 추천 챗봇"""
    print("안녕하세요! 운동 루틴 추천 챗봇입니다.")
    print("운동 루틴을 추천해드릴까요?")
    print("종료하시려면 'quit'를 입력하세요.")
    
    while True:
        user_input = input("\n사용자: ").strip()
        
        if user_input.lower() == 'quit':
            print("\n챗봇: 좋은 하루 되세요! 운동 루틴 추천 챗봇을 종료합니다.")
            break
            
        if is_workout_request(user_input):
            # 더미 사용자 정보 사용
            sample_user_info = {
                "exercise_history": 2,
                "age": 28,
                "weight": 75,
                "height": 180,
                "injuries": ["요통"],
                "goals": ["근력", "지구력"],
                "available_equipment": ["덤벨", "밴드", "맨몸운동"],
                "preferred_workout_time": "morning",
                "weekly_workout_days": 4
            }
            
            try:
                result = generate_workout_routine(sample_user_info)
                
                # 결과 출력
                print("\n챗봇: 맞춤형 운동 루틴을 추천해드리겠습니다!")
                print("\n=== 주간 운동 계획 ===")
                
                # 주간 스케줄 출력
                for day, schedule in result["workout_plan"]["weekly_schedule"].items():
                    print(f"\n{day.upper()}:")
                    print(f"운동 유형: {schedule['type']}")
                    if "exercises" in schedule:
                        print("추천 운동:")
                        for exercise in schedule["exercises"]:
                            print(f"- {exercise['name']}")
                            print(f"  세트: {exercise['sets']}")
                            print(f"  반복: {exercise['reps']}")
                            print(f"  휴식: {exercise['rest']}")
                            if "research_evidence" in exercise:
                                print("  연구 근거:")
                                for evidence in exercise["research_evidence"]:
                                    print(f"  * {evidence}")
                
                print("\n추가 권장사항:")
                for exercise in result["workout_plan"]["weekly_schedule"]["monday"]["exercises"]:
                    if "recommendations" in exercise:
                        print(f"- {exercise['recommendations']}")
                
            except Exception as e:
                print(f"\n챗봇: 죄송합니다. 운동 루틴을 생성하는 중 오류가 발생했습니다: {str(e)}")
        else:
            print("\n챗봇: 죄송합니다. 운동 루틴 추천에 대해 말씀해 주시겠어요?")
            print("예시: '운동 루틴 추천해줘', '트레이닝 프로그램 만들어줘'") 