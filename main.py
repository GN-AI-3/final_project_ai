from src.agents.workout_agent import chat_with_workout_agent
from src.workflows.workout_workflow import create_workout_workflow
from src.models.state_models import WorkoutState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import json

def convert_messages_to_serializable(messages):
    """메시지 객체들을 직렬화 가능한 형태로 변환"""
    serializable_messages = []
    for msg in messages:
        if isinstance(msg, (AIMessage, HumanMessage, ToolMessage)):
            msg_dict = {
                "type": msg.__class__.__name__,
                "content": msg.content,
                "additional_kwargs": msg.additional_kwargs
            }
            serializable_messages.append(msg_dict)
        else:
            serializable_messages.append(str(msg))
    return serializable_messages

def main():
    """메인 실행 함수"""
    print("운동 루틴 추천 챗봇에 오신 것을 환영합니다!")
    print("운동 루틴을 추천받으시려면 '운동 루틴 추천해줘'라고 입력해주세요.")
    print("종료하려면 'quit'를 입력해주세요.")
    
    while True:
        user_input = input("\n사용자: ").strip()
        
        if user_input.lower() == 'quit':
            print("챗봇을 종료합니다.")
            break
            
        if "운동 루틴 추천해줘" in user_input:
            # 워크플로우 생성
            workflow = create_workout_workflow()
            
            # 초기 상태 설정
            initial_state: WorkoutState = {
                "messages": [],
                "user_info": {
                    "exercise_history": "1년",
                    "age": 25,
                    "weight": 70,
                    "height": 175,
                    "injuries": ["허리 통증"],
                    "goals": ["근력 향상", "체력 향상"],
                    "available_equipment": ["덤벨", "바벨", "매트"],
                    "preferred_workout_time": "아침",
                    "weekly_workout_days": 3
                },
                "current_step": "start",
                "workout_plan": {},
                "feedback": {}
            }
            
            # 워크플로우 실행
            final_state = workflow.invoke(initial_state)
            
            # 운동 계획 출력
            print("\n챗봇: 안녕하세요! 맞춤형 운동 계획을 만들어드리겠습니다.")
            print(f"\n=== 주 {final_state['workout_plan']['weekly_workout_days']}회 운동 계획 ===")
            
            for workout_day in final_state["workout_plan"]["workout_days"]:
                print(f"\n{workout_day['day']}")
                print("-" * 50)
                for exercise in workout_day["exercises"]:
                    print(f"{exercise['name']}")
                    print(f"- 세트: {exercise['sets']}세트")
                    print(f"- 반복: {exercise['reps']}회")
                    print(f"- 휴식: {exercise['rest']}")
                    print()
            
            print("\n운동 계획에 대해 추가로 궁금하신 점이 있으시다면 말씀해 주세요!")
        else:
            print("죄송합니다. 운동 루틴 추천만 가능합니다. '운동 루틴 추천해줘'라고 입력해주세요.")

if __name__ == "__main__":
    main() 