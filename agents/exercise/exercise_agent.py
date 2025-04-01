from typing import Dict, Any
from ..base_agent import BaseAgent
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .workflows.workout_workflow import create_workout_workflow
from .models.state_models import WorkoutState
from .main import main

class ExerciseAgent(BaseAgent):
    @staticmethod
    def convert_messages_to_serializable(messages):
        """메시지 객체를 직렬화 가능한 형태로 변환"""
        serializable_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                serializable_messages.append(msg)
            elif isinstance(msg, (AIMessage, HumanMessage, ToolMessage)):
                serializable_messages.append({
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                })
            else:
                serializable_messages.append(str(msg))
        return serializable_messages

    async def process(self, message: str) -> Dict[str, Any]:
        """메인 실행 함수"""
        workflow = create_workout_workflow()
        
        # 초기 상태 설정
        initial_state: WorkoutState = {
            "messages": [{"type": "human", "content": message}],
            "user_info": {
                "user_id": "1"
            },
            "current_step": "",
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

        # response = main()
        # return {"type": "exercise", "response": response.content} 