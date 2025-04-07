from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
import os
import openai

class Supervisor:
    def __init__(self, model: ChatOpenAI):
        self.model = model
        
        # 모델 안정성을 위해 직접 API 키 설정
        # SecretStr 타입이면 문자열로 변환
        if hasattr(model, 'openai_api_key'):
            api_key = model.openai_api_key
            # SecretStr 객체인 경우 문자열로 변환
            if hasattr(api_key, 'get_secret_value'):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key
            
        # 직접 OpenAI 클라이언트 초기화
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        self.agents = {
            "exercise": ExerciseAgent(model),
            "food": FoodAgent(model),
            "schedule": ScheduleAgent(model),
            "motivation": MotivationAgent(model),
            "general": GeneralAgent(model)
        }
        
    async def analyze_message(self, message: str) -> str:
        # LangChain 대신 직접 OpenAI API 호출
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """다음 카테고리 중 하나로 메시지를 분류해주세요:
                    - exercise: 운동, 운동 방법, 운동 효과 등
                    - food: 식단, 영양, 음식 등
                    - schedule: PT 일정 등록, 수정, 취소 등
                    - motivation: 감정적 어려움, 동기부여가 필요한 내용, 우울함, 좌절, 불안 등
                    - general: 위 카테고리에 속하지 않는 일반적인 대화
                    
                    응답은 위 카테고리 중 하나만 반환해주세요."""},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            # 응답에서 카테고리 추출
            response_text = response.choices[0].message.content.strip().lower()
            
            # 유효한 카테고리인지 확인
            valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
            if response_text not in valid_categories:
                # 정확히 일치하는 카테고리가 없으면 각 카테고리 키워드 확인
                if "운동" in message or "체육" in message:
                    return "exercise"
                elif "식단" in message or "음식" in message or "영양" in message:
                    return "food"
                elif "일정" in message or "계획" in message or "시간" in message:
                    return "schedule"
                elif "힘들" in message or "슬프" in message or "우울" in message or "불안" in message or "좌절" in message:
                    return "motivation"
                else:
                    return "general"
            
            return response_text
        except Exception as e:
            print(f"메시지 분류 오류: {str(e)}")
            # 오류 발생 시 일반 카테고리로 처리
            return "general"
    
    async def process(self, message: str) -> Dict[str, Any]:
        try:
            # 감정 단어를 포함하는 메시지는 우선 동기부여 에이전트로 처리
            emotional_keywords = ["힘들", "슬프", "우울", "불안", "좌절", "스트레스", "자신감", "의욕", "무기력"]
            if any(keyword in message.lower() for keyword in emotional_keywords):
                try:
                    return await self.agents["motivation"].process(message)
                except Exception as e:
                    print(f"동기부여 에이전트 오류: {str(e)}")
                    # 동기부여 에이전트 오류 시 일반 처리로 진행
            
            # 일반 처리 진행
            category = await self.analyze_message(message)
            agent = self.agents.get(category, self.agents["general"])
            
            try:
                return await agent.process(message)
            except Exception as e:
                print(f"에이전트 처리 오류 ({category}): {str(e)}")
                # 오류 발생 시 일반 에이전트로 대체
                if category != "general":
                    return await self.agents["general"].process(message)
                else:
                    return {
                        "type": "general",
                        "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다른 질문으로 다시 시도해주세요."
                    }
        except Exception as e:
            print(f"처리 중 오류: {str(e)}")
            return {
                "type": "general",
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다른 질문으로 다시 시도해주세요."
            } 