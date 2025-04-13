"""
Supervisor 모듈
에이전트 관리, 분류, 실행을 총괄하는 모듈입니다.
LangGraph 기반 다중 에이전트 처리를 지원합니다.
"""

import logging
import traceback
import json
import time
import asyncio
import uuid
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable, TypedDict

# LangChain & LangGraph 임포트
from langchain_core.language_models import BaseChatModel
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, chain
from langgraph.graph import StateGraph, END

# 대화 내역 관리자 임포트
from chat_history_manager import ChatHistoryManager

# OpenAI 및 관련 모듈 임포트
try:
    import openai
    from langchain_openai import ChatOpenAI
except ImportError:
    logging.warning("OpenAI 관련 라이브러리를 찾을 수 없습니다.")

# 로깅 설정
def setup_logging():
    """LangGraph 모듈에 대한 로깅을 설정합니다."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 핸들러가 이미 설정되어 있는지 확인
    if logger.hasHandlers():
        return logger
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 설정
    try:
        log_file = "supervisor.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s (%(filename)s:%(lineno)d)',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"로그 파일 설정 중 오류 발생: {str(e)}")
    
    return logger

# 로그 초기화
logger = setup_logging()
logger.info("Supervisor 모듈 초기화 완료")

# 전역 변수로 model과 agents 선언
model = None
agents = {}

# 최대 응답 길이 설정
MAX_RESPONSE_LENGTH = 8000

# 카테고리 분류를 위한 시스템 프롬프트
CATEGORY_SYSTEM_PROMPT = """당신은 사용자의 메시지를 분석하고 적절한 카테고리로 분류하는 도우미입니다.
사용자의 메시지를 다음 카테고리 중 적합한 카테고리를 모두 찾아서 분류해야 합니다:

1. exercise: 운동, 피트니스, 트레이닝, 근육, 스트레칭, 체력, 운동 루틴, 운동 계획, 운동 방법, 요일별 운동 추천, 운동 일정 계획, 운동 프로그램 등에 관련된 질문
2. food: 음식, 식단, 영양, 요리, 식품, 건강식, 식이요법, 다이어트 식단, 영양소 등에 관련된 질문
3. schedule: PT 예약, 트레이닝 세션 일정, 코치 미팅 스케줄, 피트니스 클래스 등록, 헬스장 방문 일정 등 실제 일정 관리에 관련된 질문
4. motivation: 동기 부여, 의지 강화, 습관 형성, 마음가짐, 목표 설정 등에 관련된 질문
5. general: 위 카테고리에 명확하게 속하지 않지만 건강/피트니스와 관련된 일반 대화

분류 시 주의사항:
- 운동 루틴이나 운동 계획, 요일별 운동 추천, 주간 운동 계획 등은 모두 schedule이 아닌 exercise 카테고리로 분류하세요.
- 요일별 식단이나 식단 계획은 food 카테고리로 분류하세요.
- schedule 카테고리는 실제 PT 예약, 코치 미팅, 피트니스 클래스 참여와 같은 구체적인 일정 관리에만 사용하세요.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천해줘"와 같은 질문은 exercise 카테고리입니다.
- "이번주 월,수,금에 운동할건데 식단 추천해줘"와 같은 질문은 food 카테고리입니다.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천이랑 식단 같이 짜줘"와 같은 질문은 exercise와 food 카테고리입니다.

제공된 사용자 메시지를 분석하고 관련된 모든 카테고리를 JSON 배열 형식으로 반환하세요.
예: ["exercise", "food"], ["food"], ["motivation"]

사용자 메시지가 여러 카테고리에 해당할 수 있으며, 최대 3개까지의 관련 카테고리를 반환하세요.
동시에 여러 주제를 언급한 경우, 관련된 모든 카테고리를 포함해야 합니다.
예를 들어, "운동과 식단 계획을 알려줘"는 ["exercise", "food"]와 같이 분류될 수 있습니다."""

# 에이전트 프롬프트 템플릿 (대화 맥락 포함)
AGENT_CONTEXT_PROMPT = """당신은 전문 AI 피트니스 코치입니다. 이전 대화 내용을 고려하여 사용자의 질문에 답변해 주세요.

이전 대화 내역:
{chat_history}

사용자의 새 질문: {message}

답변 시 이전 대화의 맥락을 고려하여 일관되고 개인화된 답변을 제공하세요."""

# ======== 1. 상태 클래스 정의 ========
class SupervisorStateDict(TypedDict, total=False):
    """LangGraph용 Supervisor 상태 타입 정의"""
    request_id: str
    message: str
    email: Optional[str]
    chat_history: List[Dict[str, Any]]
    categories: List[str]
    selected_agents: List[str]
    agent_outputs: Dict[str, Any]
    agent_errors: Dict[str, str]
    response: str
    response_type: str
    error: Optional[str]
    metrics: Dict[str, Any]
    used_nodes: List[str]
    start_time: float

class SupervisorState:
    """LangGraph 워크플로우의 상태를 관리하는 클래스"""
    
    def __init__(self, 
                message: str = "", 
                email: str = None, 
                chat_history: List[Dict[str, Any]] = None,
                start_time: float = None,
                context: Dict[str, Any] = None):
        """
        상태 초기화
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일
            chat_history: 대화 내역
            start_time: 처리 시작 시간
            context: 추가 컨텍스트 정보
        """
        # 기본 정보
        self.request_id = str(uuid.uuid4())
        self.message = message
        self.email = email
        self.chat_history = chat_history or []
        self.start_time = start_time or time.time()
        
        # 라우팅 관련
        self.categories = []
        self.selected_agents = []
        
        # 에이전트 실행 관련
        self.agent_outputs = {}
        self.agent_errors = {}
        
        # 응답 관련
        self.response = ""
        self.response_type = "general"
        
        # 오류 관련
        self.error = None
        
        # 메트릭
        self.metrics = {}
        
        # 추가 컨텍스트 정보
        self.context = context or {}
        
        # 사용된 노드 추적
        self.used_nodes = []
    
    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> 'SupervisorState':
        """딕셔너리에서 상태 객체 생성"""
        state = cls()
        
        for key, value in state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        return state
    
    def to_dict(self) -> Dict[str, Any]:
        """상태를 딕셔너리로 변환"""
        return {
            "request_id": self.request_id,
            "message": self.message,
            "email": self.email,
            "chat_history": self.chat_history,
            "categories": self.categories,
            "selected_agents": self.selected_agents,
            "agent_outputs": self.agent_outputs,
            "agent_errors": self.agent_errors,
            "response": self.response,
            "response_type": self.response_type,
            "error": self.error,
            "metrics": self.metrics,
            "context": self.context,
            "used_nodes": self.used_nodes
        }
    
    def set(self, key: str, value: Any) -> None:
        """상태 값 설정"""
        setattr(self, key, value)

# ======== 2. Supervisor 클래스 정의 ========
class Supervisor:
    """
    에이전트 관리 및 메시지 처리를 담당하는 수퍼바이저 클래스
    """
    def __init__(self, model):
        """모델과 에이전트 초기화"""
        self.model = model
        self.chat_history_manager = ChatHistoryManager()
        
        # API 키 설정
        if hasattr(model, 'openai_api_key'):
            api_key = model.openai_api_key
            if hasattr(api_key, 'get_secret_value'):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key
            
        # OpenAI 클라이언트
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 에이전트 초기화 (구현 필요)
        self.agents = {}
        self._init_agents()
    
    def _init_agents(self):
        """내부 메서드: 사용할 에이전트 초기화"""
        # 여기서 에이전트를 동적으로 로드하거나 초기화
        # 예: self.agents = {"exercise": ExerciseAgent(self.model), ...}
        from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
        self.agents = {
            "exercise": ExerciseAgent(self.model),
            "food": FoodAgent(self.model),
            "schedule": ScheduleAgent(self.model),
            "motivation": MotivationAgent(self.model),
            "general": GeneralAgent(self.model)
        }
    
    def get_conversation_context(self, email: str, limit: int = 5) -> str:
        """대화 내역을 문맥으로 가져오기"""
        try:
            if not email:
                logger.info("이메일이 제공되지 않아 대화 내역을 조회하지 않습니다.")
                return ""
                
            logger.info(f"대화 내역 조회 - 이메일: {email}, 개수: {limit}")
            messages = self.chat_history_manager.get_recent_messages(email, limit)
            
            if not messages:
                logger.info(f"조회된 대화 내역 없음 - 이메일: {email}")
                return ""
                
            # 대화 내역 형식화
            context = "이전 대화 내역:\n"
            for msg in messages:
                role = "사용자" if msg.get("role") == "user" else "AI"
                content = msg.get("content", "")
                if len(content) > 200:  # 길이 제한
                    content = content[:200] + "..."
                context += f"{role}: {content}\n"
            
            logger.info(f"대화 내역 조회 완료 - {len(messages)}개 메시지")
            return context
            
        except Exception as e:
            logger.error(f"대화 내역 조회 오류: {str(e)}")
            return ""
    
    async def analyze_message(self, message: str, context: str = "") -> List[str]:
        """메시지를 분석하여 카테고리 분류"""
        try:
            # 사용자 메시지 구성
            user_content = message
            if context:
                user_content = f"이전 대화 내역:\n{context}\n\n현재 메시지: {message}"
            
            # API 호출
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": CATEGORY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"분류 응답: {response_text}")
            
            # 결과 파싱
            try:
                categories = json.loads(response_text)
                
                # 유효한 카테고리 확인
                valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
                filtered_categories = [cat for cat in categories if cat in valid_categories]
                
                if not filtered_categories:
                    logger.warning(f"유효한 카테고리가 없어 'general'로 기본 설정")
                    return ["general"]
                
                logger.info(f"메시지 분류 완료: {filtered_categories}")
                return filtered_categories
                
            except json.JSONDecodeError:
                logger.error(f"JSON 파싱 실패: {response_text}")
                return await self.analyze_emotion_based(message)
                
        except Exception as e:
            logger.error(f"메시지 분석 오류: {str(e)}")
            return ["general"]
    
    async def analyze_emotion_based(self, message: str) -> List[str]:
        """감정 기반 분류 (fallback)"""
        try:
            system_content = """다음 메시지에서 감정과 내용을 분석하고 적절한 카테고리를 모두 선택해주세요:
            - motivation: 부정적 감정이 느껴지는 경우 (우울함, 좌절, 불안 등)
            - exercise: 운동 관련 내용
            - food: 음식, 식단 관련 내용
            - schedule: 일정 관련 내용
            - general: 위 어느 것에도 해당하지 않는 경우
            
            관련된 모든 카테고리를 JSON 배열 형식으로 반환하세요. 예: ["exercise", "food"]"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            response_text = response.choices[0].message.content.strip()
            
            try:
                categories = json.loads(response_text)
                valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
                filtered_categories = [cat for cat in categories if cat in valid_categories]
                
                if not filtered_categories:
                    return ["general"]
                    
                return filtered_categories
                
            except json.JSONDecodeError:
                # 단일 카테고리 응답인 경우 처리
                category = response_text.lower()
                valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
                
                return [category] if category in valid_categories else ["general"]
            
        except Exception as e:
            logger.error(f"감정 분석 오류: {str(e)}")
            return ["general"]
    
    async def process(self, message: str, member_id: int = None, email: str = None) -> Dict[str, Any]:
        """메시지 처리 메인 메서드"""
        request_id = str(uuid.uuid4())
        try:
            logger.info(f"[{request_id}] 메시지 처리 시작 - 이메일: {email or '없음'}, 메시지: {message[:50]}...")
            
            # 이전 대화 내역 가져오기
            context = ""
            chat_history = []
            if email:
                # 대화 내역 조회 (문자열 컨텍스트용)
                context = self.get_conversation_context(email)
                
                # 대화 내역 조회 (에이전트 전달용)
                if hasattr(self.chat_history_manager, 'get_formatted_history'):
                    chat_history = self.chat_history_manager.get_formatted_history(email, limit=5)
                    logger.info(f"[{request_id}] 채팅 내역 조회 결과: {len(chat_history)}개 메시지")
                    
                    if chat_history and len(chat_history) > 0:
                        # 처음 및 마지막 메시지 로깅
                        first_msg = chat_history[0] if chat_history else {}
                        last_msg = chat_history[-1] if len(chat_history) > 0 else {}
                        logger.info(f"[{request_id}] 첫 번째 메시지: {first_msg.get('role')} - {first_msg.get('content', '')[:30]}...")
                        logger.info(f"[{request_id}] 마지막 메시지: {last_msg.get('role')} - {last_msg.get('content', '')[:30]}...")
            
            # 메시지 분류
            categories = await self.analyze_message(message, context)
            logger.info(f"[{request_id}] 메시지 카테고리: {categories}")
            
            # 복합 주제인 경우 에이전트별 특화 메시지 생성
            specialized_messages = {}
            if len(categories) > 1:
                specialized_messages = await self._create_specialized_messages(message, categories)
                logger.info(f"[{request_id}] 에이전트별 특화 메시지 생성 완료: {len(specialized_messages)} 개 카테고리")
            
            # 복합 카테고리 처리
            responses = []
            for category in categories:
                agent = self.agents.get(category, self.agents["general"])
                
                # 에이전트별 특화 메시지 사용
                agent_message = specialized_messages.get(category, message)
                logger.info(f"[{request_id}] 에이전트 '{category}'에 전달할 메시지: {agent_message[:50]}...")
                
                # 에이전트 호출
                try:
                    # 에이전트가 지원하는 매개변수에 따라 호출
                    if email:
                        try:
                            # 기본 처리: 채팅 내역과 함께 호출 시도
                            if hasattr(agent, 'process') and 'chat_history' in agent.process.__code__.co_varnames:
                                logger.info(f"[{request_id}] 에이전트 '{category}'에 채팅 내역과 함께 호출")
                                agent_response = await agent.process(agent_message, email=email, chat_history=chat_history)
                            # 폴백 1: 컨텍스트와 함께 호출 시도
                            elif hasattr(agent, 'process') and 'context' in agent.process.__code__.co_varnames:
                                logger.info(f"[{request_id}] 에이전트 '{category}'에 컨텍스트와 함께 호출")
                                agent_response = await agent.process(agent_message, email=email, context=context)
                            # 폴백 2: 이메일만 전달
                            else:
                                logger.info(f"[{request_id}] 에이전트 '{category}'에 이메일만 전달하여 호출")
                                agent_response = await agent.process(agent_message, email=email)
                        except TypeError as te:
                            logger.warning(f"[{request_id}] 에이전트 호출 타입 오류: {str(te)}, 기본 호출로 폴백")
                            agent_response = await agent.process(agent_message)
                    else:
                        agent_response = await agent.process(agent_message)
                    
                    if agent_response and isinstance(agent_response, dict) and "response" in agent_response:
                        # 카테고리 정보 추가
                        if "category" not in agent_response:
                            agent_response["category"] = category
                        responses.append(agent_response)
                    
                except Exception as e:
                    logger.error(f"[{request_id}] 에이전트 '{category}' 처리 오류: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # 복합 응답 처리
            if len(responses) > 1:
                # 여러 카테고리의 응답을 결합
                combined_response = self._combine_responses(responses, categories)
                response_data = {
                    "type": "_".join(categories),
                    "response": combined_response,
                    "categories": categories
                }
            elif len(responses) == 1:
                # 단일 응답 처리
                response_data = responses[0]
                if "categories" not in response_data:
                    response_data["categories"] = categories
            else:
                # 응답 없음 - 기본 응답
                response_data = {
                    "type": "general",
                    "response": f"죄송합니다. {' & '.join(categories)} 관련 요청을 처리하는 중에 문제가 발생했습니다.",
                    "categories": categories
                }
            
            # 대화 내역 저장
            if email and isinstance(response_data, dict) and "response" in response_data:
                # 사용자 메시지 저장
                await self.chat_history_manager.add_chat_entry(
                    email=email,
                    role="user",
                    content=message,
                    timestamp=time.time()
                )
                
                # AI 응답 저장 (role을 assistant로 통일)
                await self.chat_history_manager.add_chat_entry(
                    email=email,
                    role="assistant",  # 'ai'가 아닌 'assistant'로 통일
                    content=response_data["response"],
                    timestamp=time.time()
                )
            
            return response_data
            
        except Exception as e:
            logger.error(f"[{request_id}] 처리 중 심각한 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "type": "general",
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
            }
        
    async def _create_specialized_messages(self, message: str, categories: List[str]) -> Dict[str, str]:
        """
        각 카테고리별로 특화된 메시지를 생성합니다.
        
        Args:
            message: 원본 사용자 메시지
            categories: 분류된 카테고리 목록
            
        Returns:
            Dict[str, str]: 카테고리별 특화 메시지
        """
        if len(categories) <= 1:
            return {}
        
        specialized_messages = {}
        
        try:
            # 카테고리별 특화 프롬프트
            system_prompt = """당신은 사용자의 복합적인 요청을 각 전문 분야별로 특화된 요청으로 변환하는 도우미입니다.
            
사용자의 메시지는 다음 여러 카테고리에 해당합니다: {categories}

각 카테고리별로 사용자의 원래 요청을 해당 분야에만 집중한 자연스러운 요청으로 바꿔주세요. 
원래 메시지의 의도와 맥락은 유지하되, 해당 카테고리의 전문가가 자신의 분야에만 집중할 수 있도록 메시지를 수정해야 합니다.

예시:
- 원래 메시지: "운동 루틴과 식단 짜줘"
  - exercise 카테고리: "나에게 맞는 운동 루틴 짜줘"
  - food 카테고리: "운동에 맞는 식단 계획 짜줘"

- 원래 메시지: "체중 감량을 위한 운동 계획과 식단, 그리고 동기부여 방법 알려줘"
  - exercise 카테고리: "체중 감량에 효과적인 운동 계획 알려줘"
  - food 카테고리: "체중 감량을 위한 건강한 식단 추천해줘"
  - motivation 카테고리: "체중 감량을 지속할 수 있는 동기부여 방법 알려줘"

각 카테고리별 요청은 자연스러운 완전한 문장으로 작성해주세요. 
응답은 다음 JSON 형식으로 제공해주세요:

{
  "category1": "특화된 메시지1",
  "category2": "특화된 메시지2",
  ...
}

예를 들어:
{
  "exercise": "나에게 맞는 운동 루틴 짜줘",
  "food": "운동에 맞는 식단 계획 짜줘"
}"""

            # 실제 카테고리 목록 채우기
            formatted_prompt = system_prompt.format(categories=", ".join(categories))
            
            # API 호출
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            # 결과 파싱
            response_text = response.choices[0].message.content.strip()
            logger.info(f"특화 메시지 생성 응답: {response_text}")
            
            try:
                specialized_messages = json.loads(response_text)
                
                # 유효성 검사
                valid_specialized_messages = {}
                for category in categories:
                    if category in specialized_messages:
                        valid_specialized_messages[category] = specialized_messages[category]
                        logger.info(f"카테고리 '{category}'의 특화 메시지 생성: {specialized_messages[category]}")
                    else:
                        valid_specialized_messages[category] = message
                        logger.warning(f"카테고리 '{category}'의 특화 메시지 생성 실패, 원본 메시지 사용")
                
                return valid_specialized_messages
                
            except json.JSONDecodeError:
                logger.error(f"특화 메시지 JSON 파싱 실패: {response_text}")
                # 실패 시 원본 메시지 사용
                return {category: message for category in categories}
                
        except Exception as e:
            logger.error(f"특화 메시지 생성 오류: {str(e)}")
            return {category: message for category in categories}
    
    def _combine_responses(self, responses: List[Dict[str, Any]], categories: List[str]) -> str:
        """여러 에이전트의 응답을 결합"""
        try:
            # 각 에이전트 응답에 카테고리 메타데이터 추가
            formatted_responses = []
            for resp, category in zip(responses, categories):
                formatted_responses.append({
                    "category": category,
                    "response": resp.get("response", ""),
                    "is_specialized": True  # 특화된 에이전트로 간주
                })
            
            # LLM을 통한 응답 통합
            system_prompt = """당신은 여러 전문가의 답변을 하나로 통합하여 사용자에게 일관되고 유용한 응답을 제공하는 도우미입니다.

여러 전문 분야 에이전트의 응답을 통합할 때는 다음 규칙을 따라야 합니다:

1. 각 분야별 전문 에이전트의 고유한 내용을 보존하면서 자연스럽게 통합하세요.
2. 여러 에이전트가 중복된 내용을 제공한 경우, 해당 주제에 가장 특화된 에이전트의 응답을 우선적으로 선택하세요.
   - 예: 운동과 식단 모두에서 단백질 섭취를 언급했다면, 식단 전문가의 단백질 섭취 조언을 우선적으로 선택하세요.
3. 동일한 질문에 대한 다른 관점이나 조언이 있다면, 각 관점을 병합하되 충돌이 없도록 만드세요.
4. 정보를 논리적으로 구성하고, 비슷한 주제의 정보는 함께 그룹화하세요.
5. 통합된 응답은 마치 한 명의 전문가가 작성한 것처럼 일관된 어조와 스타일을 유지해야 합니다.
6. 응답이 너무 길어지지 않도록 중요하고 관련성 높은 정보만 포함하세요.
7. 필요한 경우 카테고리 간의 연결 문구를 추가하여 자연스러운 흐름을 만드세요.

최종 응답은 사용자가 여러 전문가에게 따로 물어본 것이 아니라, 모든 관련 전문성을 갖춘 한 명의 코치에게 질문한 것처럼 느껴져야 합니다."""
            
            combined_prompt = "다음은 여러 전문 분야 에이전트의 응답입니다. 이들을 자연스럽게 통합하여 하나의 종합적인 응답으로 만들어주세요:\n\n"
            
            # 카테고리별 응답 추가
            for resp in formatted_responses:
                category_name = resp["category"]
                # 카테고리별 설명 추가
                if category_name == "exercise":
                    category_desc = "운동 전문가"
                elif category_name == "food":
                    category_desc = "영양/식단 전문가"
                elif category_name == "schedule":
                    category_desc = "일정 관리 전문가"
                elif category_name == "motivation":
                    category_desc = "동기부여 전문가"
                else:
                    category_desc = "일반 상담 전문가"
                    
                combined_prompt += f"[{category_desc}의 응답]\n{resp['response']}\n\n"
            
            combined_prompt += "\n통합 응답 지침:\n"
            combined_prompt += "1. 위 전문가들의 응답을 하나의 자연스러운 답변으로 통합해주세요.\n"
            combined_prompt += "2. 중복되는 내용은 해당 분야에 특화된 전문가의 내용을 우선적으로 선택하세요.\n"
            combined_prompt += "3. 통합된 답변은 각 전문 영역의 내용이 논리적으로 연결되도록 구성하세요.\n"
            combined_prompt += "4. 모든 중요한 정보와 조언이 포함되도록 하되, 마치 한 명의 통합된 전문가가 답변하는 것처럼 작성해주세요.\n\n"
            combined_prompt += "통합된 응답:"
            
            # API 호출
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_prompt}
                ],
                temperature=0.3,  # 일관성을 위해 낮은 온도 설정
                max_tokens=1200   # 충분한 응답 길이 확보
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"응답 통합 오류: {str(e)}")
            # 오류 발생 시 단순 연결
            return "\n\n".join([resp.get("response", "") for resp in responses])

def execute_agents(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    선택된 에이전트들 실행
    """
    # 전역 변수 사용
    global agents
    
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    message = state.message
    chat_history = state.chat_history
    selected_agents = state.selected_agents
    
    start_time = time.time()
    agent_results = []
    
    try:
        logger.info(f"[{request_id}] 에이전트 실행 시작: {selected_agents}")
        
        # 선택된 에이전트가 없는 경우 기본 에이전트 사용
        if not selected_agents:
            selected_agents = ["general"]
            logger.warning(f"[{request_id}] 선택된 에이전트가 없어 기본 에이전트 사용")
        
        # 각 에이전트 순차적으로 실행
        for agent_name in selected_agents:
            if agent_name not in agents:
                logger.warning(f"[{request_id}] 에이전트 '{agent_name}' 찾을 수 없음")
                continue
                
            agent = agents[agent_name]
            agent_start_time = time.time()
            
            try:
                logger.info(f"[{request_id}] 에이전트 '{agent_name}' 실행 중")
                
                # 에이전트 실행
                agent_result = agent.process(
                    message=message,
                    chat_history=chat_history
                )
                
                # 결과 추가
                agent_results.append({
                    "agent": agent_name,
                    "result": agent_result,
                    "execution_time": time.time() - agent_start_time
                })
                
                logger.info(f"[{request_id}] 에이전트 '{agent_name}' 실행 완료 (소요시간: {time.time() - agent_start_time:.2f}초)")
                
            except Exception as e:
                logger.error(f"[{request_id}] 에이전트 '{agent_name}' 실행 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                
                # 오류 발생 시 결과에 오류 정보 추가
                agent_results.append({
                    "agent": agent_name,
                    "error": str(e),
                    "execution_time": time.time() - agent_start_time
                })
        
        # 상태 업데이트
        state.agent_results = agent_results
        state.metrics["agents_execution_time"] = time.time() - start_time
        
    except Exception as e:
        logger.error(f"[{request_id}] 에이전트 실행 과정에서 심각한 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 심각한 오류 발생 시 상태 업데이트
        state.error = f"에이전트 실행 오류: {str(e)}"
        state.metrics["agents_execution_error"] = str(e)
        state.metrics["agents_execution_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict()

def generate_response(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    에이전트 결과를 바탕으로 응답 생성
    """
    # 전역 변수 사용
    global model
    
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    agent_results = state.agent_results
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 응답 생성 시작")
        
        if not agent_results:
            raise ValueError("에이전트 결과가 없습니다.")
        
        # 유효한 결과만 추출
        valid_results = []
        for result in agent_results:
            if "error" not in result:
                valid_results.append(result)
        
        if not valid_results:
            raise ValueError("유효한 에이전트 결과가 없습니다.")
        
        # 응답 결합 (필요한 경우 응답 결합 로직 추가)
        combined_result = valid_results[0]["result"]
        
        # 응답 형식화
        response = combined_result
        if len(response) > MAX_RESPONSE_LENGTH:
            response = response[:MAX_RESPONSE_LENGTH] + "..."
        
        # 상태 업데이트
        state.response = response
        state.response_type = "text"  # 기본 응답 타입
        state.metrics["response_generation_time"] = time.time() - start_time
        
        logger.info(f"[{request_id}] 응답 생성 완료 (소요시간: {time.time() - start_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"[{request_id}] 응답 생성 과정에서 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 응답과 함께 상태 업데이트
        state.response = f"죄송합니다. 응답을 생성하는 과정에서 오류가 발생했습니다: {str(e)}"
        state.response_type = "error"
        state.metrics["response_generation_error"] = str(e)
        state.metrics["response_generation_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict()

def route_message(
    message: str,
    email: str = None,
    chat_history: List[Dict[str, str]] = None,
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하여 적절한 에이전트로 라우팅하고 응답을 생성합니다.
    
    Args:
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        chat_history: 채팅 기록 (선택 사항)
        context: 추가 컨텍스트 정보 (선택 사항)
    
    Returns:
        Dict: 응답 및 메타데이터가 포함된 딕셔너리
    """
    global agents
    
    # 초기 상태 설정
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # 채팅 기록 초기화 (없는 경우)
    if chat_history is None:
        chat_history = []
    
    # 컨텍스트 초기화 (없는 경우)
    if context is None:
        context = {}
    
    # SupervisorState 초기화
    state = SupervisorState(
        request_id=request_id,
        message=message,
        email=email,
        chat_history=chat_history,
        context=context
    )
    
    logger.info(f"[{request_id}] 메시지 처리 시작: '{message[:50]}...' (길이: {len(message)})")
    
    try:
        # 메트릭 초기화
        metrics = {
            "start_time": start_time,
            "classification_time": 0,
            "agent_execution_time": 0,
            "response_generation_time": 0,
        }
        
        # 1. 메시지 분류 및 에이전트 선택
        state_dict = state.to_dict()
        state_dict = classify_message(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 2. 선택된 에이전트 실행
        state_dict = state.to_dict()
        state_dict = execute_agents(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 3. 응답 생성
        state_dict = state.to_dict()
        state_dict = generate_response(state_dict)
        state = SupervisorState.from_dict(state_dict)
        
        # 전체 실행 시간 계산
        total_time = time.time() - start_time
        state.metrics["total_execution_time"] = total_time
        
        logger.info(f"[{request_id}] 메시지 처리 완료 (소요시간: {total_time:.2f}초)")
        
        # 채팅 기록 저장 (필요한 경우)
        if email and isinstance(state.response, str):
            new_history_item = {
                "role": "user",
                "content": message
            }
            chat_history.append(new_history_item)
            
            new_history_item = {
                "role": "assistant",
                "content": state.response
            }
            chat_history.append(new_history_item)
        
        # 결과 반환
        return {
            "request_id": state.request_id,
            "response": state.response if isinstance(state.response, str) else "",
            "response_type": state.response_type if isinstance(state.response, str) else "text",
            "categories": state.categories if isinstance(state.categories, list) else [],
            "selected_agents": state.selected_agents if isinstance(state.selected_agents, list) else [],
            "metrics": state.metrics,
            "execution_time": total_time
        }
    
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 처리 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 응답 반환
        return {
            "request_id": request_id,
            "response": f"죄송합니다. 메시지를 처리하는 과정에서 오류가 발생했습니다: {str(e)}",
            "response_type": "error",
            "categories": [],
            "selected_agents": [],
            "metrics": {"error": str(e)},
            "execution_time": time.time() - start_time
        }

def process_message(
    message: str,
    email: str = None,
    chat_history: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    사용자 메시지를 처리하여 적절한 에이전트로 라우팅하고 응답을 생성합니다.
    
    Args:
        message: 사용자 메시지
        email: 사용자 이메일 (선택 사항)
        chat_history: 채팅 기록 (선택 사항)
    
    Returns:
        Dict: 응답 및 메타데이터가 포함된 딕셔너리
    """
    # route_message 함수를 호출하여 결과 반환
    return route_message(message, email, chat_history)

def classify_message(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 메시지를 분류하여 적절한 에이전트 카테고리를 할당합니다.
    
    Args:
        state_dict: 현재 상태 딕셔너리
        
    Returns:
        Dict[str, Any]: 업데이트된 상태 딕셔너리
    """
    # 전역 변수 사용
    global model
    
    # 상태 딕셔너리로부터 SupervisorState 생성
    state = SupervisorState.from_dict(state_dict)
    
    # 상태에서 필요한 정보 추출
    request_id = state.request_id
    message = state.message
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 메시지 분류 시작: '{message[:50]}...'")
        
        # OpenAI API 호출
        try:
            # API 클라이언트 설정
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # API 호출
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": CATEGORY_SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            # 결과 파싱
            response_text = response.choices[0].message.content.strip()
            logger.info(f"LLM 분류 응답: {response_text}")
            
            try:
                # JSON 배열 파싱
                categories = json.loads(response_text)
                
                # 유효한 카테고리 목록
                valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
                
                # 유효한 카테고리만 필터링
                filtered_categories = [cat for cat in categories if cat in valid_categories]
                
                # 카테고리가 없으면 기본값 사용
                if not filtered_categories:
                    filtered_categories = ["general"]
                    logger.warning(f"[{request_id}] 유효한 카테고리가 없어 'general'로 기본 설정")
                
                # 상태 업데이트
                state.categories = filtered_categories
                state.selected_agents = filtered_categories  # 현재는 카테고리와 에이전트를 1:1로 매핑
                
                logger.info(f"[{request_id}] LLM 메시지 분류 완료: {filtered_categories}")
                
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 키워드 기반 백업 분류 방식 사용
                logger.warning(f"[{request_id}] JSON 파싱 실패: {response_text}, 백업 분류 방식 사용")
                categories = backup_keyword_classify(message)
                state.categories = categories
                state.selected_agents = categories
                logger.info(f"[{request_id}] 백업 분류 완료: {categories}")
                
        except Exception as api_e:
            # API 호출 실패 시 키워드 기반 백업 분류 방식 사용
            logger.error(f"[{request_id}] OpenAI API 호출 오류: {str(api_e)}, 백업 분류 방식 사용")
            categories = backup_keyword_classify(message)
            state.categories = categories
            state.selected_agents = categories
            logger.info(f"[{request_id}] 백업 분류 완료: {categories}")
        
        # 메트릭 기록
        state.metrics["classification_time"] = time.time() - start_time
        logger.info(f"[{request_id}] 메시지 분류 완료: {state.categories} (소요시간: {time.time() - start_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"[{request_id}] 메시지 분류 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 오류 발생 시 기본 카테고리 사용
        state.categories = ["general"]
        state.selected_agents = ["general"]
        state.metrics["classification_error"] = str(e)
        state.metrics["classification_time"] = time.time() - start_time
    
    # 상태 객체를 딕셔너리로 변환하여 반환
    return state.to_dict()

def backup_keyword_classify(message: str) -> List[str]:
    """
    키워드 기반 백업 분류 방식 (LLM 분류 실패 시 사용)
    
    Args:
        message: 사용자 메시지
    
    Returns:
        List[str]: 분류된 카테고리 목록
    """
    # 카테고리 목록
    categories = []
    
    # 키워드 기반 분류
    message_lower = message.lower()
    
    # exercise 카테고리 키워드
    exercise_keywords = ["운동", "피트니스", "트레이닝", "근육", "스트레칭", "체력", 
                        "헬스", "요가", "필라테스", "루틴", "웨이트", "유산소", 
                        "달리기", "조깅", "런닝", "운동법", "자세", "홈트"]
    
    # food 카테고리 키워드
    food_keywords = ["음식", "식단", "영양", "먹다", "음식", "요리", "식이요법", 
                    "식사", "밥", "끼니", "반찬", "다이어트", "식품", 
                    "건강식", "단백질", "탄수화물", "지방", "메뉴", "칼로리"]
    
    # schedule 카테고리 키워드
    schedule_keywords = ["일정", "예약", "스케줄", "시간", "언제", "미팅", 
                        "약속", "pt", "피티", "코치", "트레이너", "예약"]
    
    # motivation 카테고리 키워드
    motivation_keywords = ["동기", "의지", "마음", "힘들다", "좌절", "계속", 
                        "포기", "지치다", "자신감", "의욕", "열정", "슬럼프"]
    
    # exercise 카테고리 체크
    if any(keyword in message_lower for keyword in exercise_keywords):
        categories.append("exercise")
        
    # food 카테고리 체크
    if any(keyword in message_lower for keyword in food_keywords):
        categories.append("food")
        
    # schedule 카테고리 체크
    if any(keyword in message_lower for keyword in schedule_keywords):
        categories.append("schedule")
        
    # motivation 카테고리 체크
    if any(keyword in message_lower for keyword in motivation_keywords):
        categories.append("motivation")
    
    # 복합 주제 처리를 위한 추가 로직
    if "운동" in message_lower and "식단" in message_lower:
        # 운동과 식단이 모두 언급된 경우 두 카테고리에 모두 추가
        if "exercise" not in categories:
            categories.append("exercise")
        if "food" not in categories:
            categories.append("food")
    
    # 카테고리가 없으면 기본값 사용
    if not categories:
        categories = ["general"]
    
    return categories 