import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# 환경변수 로드
load_dotenv()

# 챗봇 프롬프트 템플릿 정의
prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 Question-Answering 챗봇입니다. 주어진 질문에 대한 답변을 제공해주세요."),
    MessagesPlaceholder(variable_name="chat_history"),  # 대화 기록 저장용
    ("human", "#Question:\n{question}")  # 사용자 입력
])

# LLM 모델 초기화
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

# 챗봇 체인 구성
chain = prompt | llm | StrOutputParser()

# 세션별 대화 기록 저장소
store = {}

def get_session_history(session_ids):
    """세션 ID에 해당하는 대화 기록을 반환하는 함수"""
    print(f"[대화 세션ID]: {session_ids}")
    if session_ids not in store:
        store[session_ids] = ChatMessageHistory()
    return store[session_ids]

# 대화 기록이 포함된 체인 생성
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="question",
    history_messages_key="chat_history"
)

def print_chat_response(question, response):
    """챗봇 응답을 포맷팅하여 출력하는 함수"""
    print("\n" + "="*50)
    print(f"질문: {question}")
    print("-"*50)
    print(f"응답: {response}")
    print("="*50 + "\n")

# 테스트 대화 1: 사용자 정보 입력
response1 = chain_with_history.invoke(
    {"question": "나의 이름은 테디입니다."},
    config={"configurable": {"session_id": "abc123"}}
)
print_chat_response("나의 이름은 테디입니다.", response1)

# 테스트 대화 2: 이전 대화를 참고한 질문
response2 = chain_with_history.invoke(
    {"question": "내 이름이 뭐라고?"},
    config={"configurable": {"session_id": "abc123"}}
)
print_chat_response("내 이름이 뭐라고?", response2)