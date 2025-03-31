<<<<<<< HEAD
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from agents.supervisor import Supervisor

async def main():
    # 환경 변수 로드
    load_dotenv()
    
    # OpenAI 모델 초기화
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0
    )
    
    # Supervisor 초기화
    supervisor = Supervisor(model)
    
    print("안녕하세요! 운동, 식단, 일정, 일반적인 대화에 대해 도움을 드릴 수 있습니다.")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.")
    
    while True:
        user_input = input("\n사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            print("대화를 종료합니다. 좋은 하루 되세요!")
            break
            
        if not user_input:
            continue
            
        try:
            response = await supervisor.process(user_input)
            print(f"\n{response['type'].upper()} 전문가: {response['response']}")
        except Exception as e:
            print(f"\n오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
=======
from dotenv import load_dotenv
from food_agent.workflow import run_workflow
from food_agent.nodes import UserState



# 환경 변수 로드 (필요한 경우)
load_dotenv()
def main():
    # 초기 상태 설정
    initial_state: UserState = {
        "user_data": {
            "weight": 70.0,  # kg
            "height": 170.0,  # cm
            "age": 30,
            "gender": "남성",
            "activity_level": "보통",
            "goal": "체중 유지",
            "target_foods": ["닭가슴살", "현미", "브로콜리"]
        },
        "current_action": "start",
        "messages": [],
        "context": {},
        "bmr": 0.0,
        "tdee": 0.0,
        "nutrition_plan": {},
        "meal_plan": []
    }
    
    # 워크플로우 실행
    run_workflow(initial_state)

if __name__ == "__main__":
    main() 
>>>>>>> d85f114497a3c8ba63cd237fdfd6ca68bd206310
