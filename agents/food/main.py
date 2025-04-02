from dotenv import load_dotenv
from agents.agent_food.workflow import run_workflow
from agents.agent_food.nodes import UserState


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