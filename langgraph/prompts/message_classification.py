"""
메시지 분류를 위한 프롬프트 템플릿
"""

from langchain.prompts import PromptTemplate

MESSAGE_CLASSIFICATION_TEMPLATE = """
다음 사용자 메시지를 분석하여 관련된 카테고리를 찾고, 각 카테고리별로 적절한 메시지를 생성해주세요.

사용자 메시지: {message}

가능한 카테고리:
- exercise: 운동, 피트니스, 트레이닝, 근육 관련 질문
- food: 음식, 식단, 영양 관련 질문
- diet: 다이어트, 체중 감량, 체지방 관련 질문
- schedule: 운동 일정, 루틴, 계획 관련 질문
- motivation: 동기 부여, 의지력, 습관 형성 관련 질문
- general: 위 카테고리에 해당하지 않는 일반적인 질문

다음 JSON 형식으로 응답해주세요:
{{
    "categories": ["카테고리1", "카테고리2", ...],
    "messages": {{
        "exercise": "운동 관련 메시지",
        "food": "식단 관련 메시지",
        "diet": "다이어트 관련 메시지",
        "schedule": "일정 관련 메시지",
        "motivation": "동기부여 관련 메시지",
        "general": "일반 메시지"
    }}
}}

각 카테고리에 대한 메시지는 원래 메시지의 의도를 유지하면서 해당 카테고리에 특화된 자연스러운 질문으로 변환해주세요.
예를 들어, "루틴이랑 식단 짜줘"라는 메시지가 있다면:
- exercise: "운동 루틴을 추천해주세요"
- food: "식단을 추천해주세요"
"""

message_classification_prompt = PromptTemplate(
    input_variables=["message"],
    template=MESSAGE_CLASSIFICATION_TEMPLATE
) 