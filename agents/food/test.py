import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import asyncio
from agents.food.new_agent_graph import run_super_agent

# ✅ 테스트용 자연어 입력 리스트
test_inputs = [
    # "오늘 아침에 닭가슴살 150g 먹었어",
    # "점심에 고구마랑 달걀 먹었어",
    # "다이어트 식단 추천해줘",
    # "하루 식단을 맞춰줘",
    # "주간 식단 짜줘",
    # "내 알레르기 정보 저장해줘 견과류",
    # "오늘 저녁은 무엇을 먹으면 좋을까?",
    # "어제 기록한 식사 보여줘",
    # "오늘 하루 목표 칼로리 알려줘",
    "탄수화물 많은 음식 추천해줘",
    # "아침 점심 저녁 추천해줘",
    # "점심에 소고기랑 샐러드 먹음 기록해줘",
    # "하루 단백질 목표량 알려줘",
    # "일주일 벌크업 식단 만들어줘",
    # "견과류 알레르기 있는데 추천 식단 줘",
    # "단백질 높은 식품 추천해줘",
    # "점메추",
    "탄수화물이 낮고 비타민이 높은 식품을 추천해줘",
    # "오늘 목표 칼로리 알려줘",
        # "오늘 목표 지방 알려줘",
        # "오늘 목표에 부족한한 채소 알려줘",
        "30대 남성에 단백질 섭취 비중중"
]

# ✅ 성공/실패 기준
def is_successful_response(response: str) -> bool:
    # 단순 기준: "❌", "오류" 같은 단어가 없으면 성공
    fail_keywords = ["❌", "오류", "에러", "실패"]
    return not any(keyword in response for keyword in fail_keywords)

# ✅ 테스트 실행 함수
async def test_agent_success_rate():
    total_tests = len(test_inputs)
    success_count = 0

    for i, input_text in enumerate(test_inputs, 1):
        print(f"🔵 [{i}/{total_tests}] 입력: {input_text}")
        try:
            response = await run_super_agent(user_input=input_text, member_id=4)
            print(f"🟢 결과: {response[:200]}...")  # 일부만 출력
            if is_successful_response(response):
                success_count += 1
            else:
                print("⚠️ 실패 감지")
        except Exception as e:
            print(f"❌ 에러 발생: {e}")

        print("-" * 50)

    success_rate = (success_count / total_tests) * 100
    print(f"\n✅ 총 테스트 수: {total_tests}")
    print(f"✅ 성공 수: {success_count}")
    print(f"✅ 성공률: {success_rate:.2f}%")

# ✅ 실행
if __name__ == "__main__":
    asyncio.run(test_agent_success_rate())
