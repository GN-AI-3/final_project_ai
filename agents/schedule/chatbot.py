import os
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import LLMs, get_model_name

from tools import tools, get_user_schedule


# LLM 초기화
MODEL_NAME = get_model_name(LLMs.GPT4)

# 시스템 프롬프트 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
prompt_file_path = os.path.join(current_dir, "prompt_kr.txt")

with open(prompt_file_path, "r", encoding="utf-8") as file:
    system_prompt = file.read().strip()


def call_chatbot(messages: List[BaseMessage]) -> str:
    """챗봇을 호출하여 응답을 생성합니다."""
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
        
        # 최초 실행 시에는 예약 조회를 하지 않음
        if len(messages) == 1 and messages[0].content == "안녕하세요?":
            return response
            
        # pt_linked_id = 1로 고정하여 예약 조회
        response = get_user_schedule.invoke(input="5")
        
        return response
    except Exception as e:
        return f"죄송합니다. 오류가 발생했습니다: {str(e)}" 