from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import LLMs, get_model_name
from tools import tools, extract_name, get_user_schedule

# LLM 초기화
MODEL_NAME = get_model_name(LLMs.GPT4)

# 시스템 프롬프트 로드
with open("prompt_kr.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read().strip()

def call_chatbot(messages: List[BaseMessage]) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    model = ChatOpenAI(model=MODEL_NAME, temperature=0).bind_tools(tools)
    chain = prompt | model | StrOutputParser()
    try:
        response = chain.invoke({"messages": messages})
        
        # 사용자 이름으로 예약 조회
        last_message = messages[-1].content
        extracted_name = extract_name.invoke(input=last_message)
        if extracted_name:
            response = get_user_schedule.invoke(input=extracted_name)
        elif not response or response.strip() == "":
            response = "죄송합니다. 입력하신 이름을 찾을 수 없습니다. 다시 시도해 주세요."
        
        return response
    except Exception as e:
        return f"죄송합니다. 오류가 발생했습니다: {str(e)}" 