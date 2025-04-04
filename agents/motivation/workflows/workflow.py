from typing import Dict, Any, TypedDict, List, Annotated, Literal
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from ..prompts.prompt_templates import get_cheer_prompt, UNIFIED_PROMPT, SYSTEM_QUERY_RESPONSE
import os
import re

# 상태 타입 정의
class MotivationState(TypedDict):
    user_message: str
    emotion: str
    emotion_intensity: float
    need_motivation: bool
    response: str

# 시스템 관련 질문인지 확인하는 함수
def is_system_query(message: str) -> bool:
    """사용자 메시지가 시스템 관련 질문인지 확인합니다."""
    # 시스템 관련 질문 패턴
    system_patterns = [
        r'프롬프트.{0,15}(뭐|무엇|어떻게|어떤)',
        r'프로젝트.{0,15}(구조|내부|설계|디자인)',
        r'권한',
        r'인증',
        r'로그인',
        r'계정',
        r'(API|서버|데이터|데이터베이스).{0,15}(구조|설정|설계)',
        r'gpt.{0,15}(사용|연결)',
        r'(코드|소스).{0,15}(보여|알려|설명)',
        r'비밀번호',
        r'토큰',
        r'키',
        r'어떻게.{0,15}(만들었|구현|개발)',
        r'(내부|안|속).{0,15}(어떻게|어떤식|어떤)',
        r'시스템.{0,15}(구조|작동|설계)',
        r'어떤.{0,15}(기술|언어|프레임워크)',
        r'데이터(베이스)?',
        r'db',
        r'api',
        r'서버',
        r'환경'
    ]
    
    # 패턴과 메시지 매칭 확인
    for pattern in system_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    
    return False

# 응원 요청인지 확인하는 함수
def is_cheer_request(message: str) -> bool:
    """사용자 메시지가 응원 요청인지 확인합니다."""
    # 응원 요청 패턴
    cheer_patterns = [
        r'응원.{0,10}해',
        r'힘내라',
        r'힘을?\s?주',
        r'격려.{0,5}해',
        r'용기.{0,5}줘',
        r'한\s?마디만',
        r'파이팅',
        r'화이팅',
        r'fighting',
        r'cheer'
    ]
    
    # 패턴과 메시지 매칭 확인
    for pattern in cheer_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    
    return False

# 감정에 따른 대응 함수
def generate_emotional_response(user_message: str, emotion: str, intensity: float) -> str:
    """감정에 기반한 동기부여 메시지를 생성합니다."""
    try:
        # LangChain 모델 초기화
        model = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            streaming=False,
            max_tokens=500
        )
        
        # 응원 요청 확인
        if is_cheer_request(user_message):
            # 응원 프롬프트 사용
            prompt_template = get_cheer_prompt()
        else:
            # 통합 동기부여 프롬프트 사용
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", UNIFIED_PROMPT),
                ("human", f"사용자 감정: {emotion} (강도: {intensity})\n\n사용자 메시지: {user_message}")
            ])
        
        # 응원 프롬프트일 경우에만 변수 치환 필요
        if is_cheer_request(user_message):
            formatted_messages = prompt_template.format_messages(
                message=user_message,
                emotion=emotion,
                intensity=str(intensity)
            )
        else:
            formatted_messages = prompt_template.format_messages()
        
        # API 호출
        response = model.invoke(formatted_messages)
        return response.content
        
    except Exception as e:
        print(f"동기부여 응답 생성 오류: {str(e)}")
        return "힘든 시간을 보내고 계시는군요. 지금은 어렵지만, 모든 어려움은 지나갑니다. 작은 걸음부터 시작해보세요."

# 일반 대화 응답 함수
def generate_general_response(user_message: str) -> str:
    """일반적인 응답을 생성합니다."""
    try:
        # LangChain 모델 초기화
        model = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            streaming=False,
            max_tokens=500
        )
        
        # LangChain 프롬프트 생성
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 친절하고 도움이 되는 AI 어시스턴트입니다. 사용자에게 도움이 될 일반적인 응답을 제공하세요."),
            ("human", "{message}")
        ])
        
        # 프롬프트 포맷팅
        formatted_messages = prompt.format_messages(
            message=user_message
        )
        
        # API 호출
        response = model.invoke(formatted_messages)
        return response.content
        
    except Exception as e:
        print(f"일반 응답 생성 오류: {str(e)}")
        return "죄송합니다. 응답을 생성하는 데 문제가 발생했습니다. 다른 질문을 해주시겠어요?"

# 통합 처리 함수
def process_message(state: MotivationState) -> MotivationState:
    """사용자 메시지를 처리하고 적절한 응답을 생성합니다."""
    result = state.copy()
    
    # 기본값 설정
    user_message = state.get("user_message", "")
    emotion = state.get("emotion", "neutral")
    intensity = state.get("emotion_intensity", 0.5)
    need_motivation = state.get("need_motivation", False)
    
    # 시스템 관련 질문 확인 (가장 먼저 체크)
    if is_system_query(user_message):
        # 시스템 관련 질문 응답 생성
        model = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.5,
            streaming=False,
            max_tokens=300
        )
        
        # 시스템 보안 응답 프롬프트 설정
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_QUERY_RESPONSE),
            ("human", user_message)
        ])
        
        # 응답 생성
        formatted_messages = prompt.format_messages()
        response = model.invoke(formatted_messages)
        result["response"] = response.content
        return result
    
    # 응원 요청 확인
    is_cheer = is_cheer_request(user_message)
    
    # 응답 생성
    if is_cheer:
        # 응원 메시지 생성
        response_text = generate_emotional_response(user_message, emotion, intensity)
    elif need_motivation and emotion != "neutral":
        # 감정적 응답 생성
        response_text = generate_emotional_response(user_message, emotion, intensity)
    else:
        # 일반 응답 생성
        response_text = generate_general_response(user_message)
    
    # 결과 업데이트
    result["response"] = response_text
    
    return result

# 워크플로우 생성 함수 (간소화)
def create_workflow():
    """동기부여 워크플로우를 생성합니다."""
    return process_message 