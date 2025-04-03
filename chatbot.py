import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
from langchain_core.chat_history import InMemoryChatMessageHistory

# 환경변수 로드
load_dotenv()

# 챗봇 프롬프트 템플릿 정의
prompt = ChatPromptTemplate.from_template(
    """You are an assistant for question-answering tasks.
    Use the following pieces of retrieved context to answer the question.
    If you don't know the answer, just say that you don't know.
    Answer in Korean.

    #Previous Chat History:
    {chat_history}

    #Question:
    {question}

    #Answer:
    """
)

# LLM 모델 초기화
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

# 챗봇 체인 구성
chain = (
    {
        "question": itemgetter("question"),
        "chat_history": itemgetter("chat_history"),
    }
    | prompt
    | llm
    | StrOutputParser()
)

# 세션별 대화 기록 저장소
chats_by_session_id  = {}

def get_chat_history(session_id: str) -> InMemoryChatMessageHistory:
    """주어진 세션 ID에 대한 대화 기록을 반환하는 함수"""
    chat_history = chats_by_session_id.get(session_id)
    if chat_history is None:
        chat_history = InMemoryChatMessageHistory()
        chats_by_session_id[session_id] = chat_history
    return chat_history

# 대화 기록이 포함된 체인 생성
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_chat_history,
    input_messages_key="question",
    history_messages_key="chat_history"
)

def chat_with_bot():
    """사용자와 챗봇이 대화를 주고받는 함수"""
    print("챗봇과 대화를 시작합니다. 종료하려면 '종료'를 입력하세요.")
    session_id = "user_session"  # 세션 ID 설정
    
    while True:
        user_input = input("\n당신: ")
        
        if user_input.lower() == "종료":
            print("대화를 종료합니다.")
            break
            
        response = chain_with_history.invoke(
            {"question": user_input},
            config={"configurable": {"session_id": session_id}}
        )
        print(f"응답: {response}\n")

if __name__ == "__main__":
    chat_with_bot()