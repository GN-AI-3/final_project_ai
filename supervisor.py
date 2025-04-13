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

# 카테고리 분류를 위한 시스템 프롬프트
CATEGORY_SYSTEM_PROMPT = """당신은 사용자의 메시지를 분석하고 적절한 카테고리로 분류하는 도우미입니다.
사용자의 메시지를 다음 카테고리 중 적합한 카테고리를 모두 찾아서 분류해야 합니다:

1. exercise: 운동, 피트니스, 트레이닝, 근육, 스트레칭, 체력, 운동 루틴, 운동 계획, 운동 방법, 요일별 운동 추천, 운동 일정 계획, 운동 프로그램 등에 관련된 질문
2. food: 음식, 식단, 영양, 요리, 식품, 건강식, 식이요법, 다이어트 식단, 영양소 등에 관련된 질문
3. diet: 체중 감량, 체중 조절, 칼로리 관리, 체지방 감소, 체형 관리 목표 등에 관련된 질문
4. schedule: PT 예약, 트레이닝 세션 일정, 코치 미팅 스케줄, 피트니스 클래스 등록, 헬스장 방문 일정 등 실제 일정 관리에 관련된 질문
5. motivation: 동기 부여, 의지 강화, 습관 형성, 마음가짐, 목표 설정 등에 관련된 질문
6. general: 위 카테고리에 명확하게 속하지 않지만 건강/피트니스와 관련된 일반 대화

분류 시 주의사항:
- 운동 루틴이나 운동 계획, 요일별 운동 추천, 주간 운동 계획 등은 모두 schedule이 아닌 exercise 카테고리로 분류하세요.
- 요일별 식단이나 식단 계획은 food 카테고리로 분류하세요.
- schedule 카테고리는 실제 PT 예약, 코치 미팅, 피트니스 클래스 참여와 같은 구체적인 일정 관리에만 사용하세요.
- diet 카테고리는 체중 감량이나 체형 관리 목표에 관한 내용으로 제한하세요.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천해줘"와 같은 질문은 exercise 카테고리입니다.
- "이번주 월,수,금에 운동할건데 식단 추천해줘"와 같은 질문은 food 카테고리입니다.
- "이번주 월,수,금에 운동할건데 요일별로 운동 추천이랑 식단 같이 짜줘"와 같은 질문은 exercise와 food 카테고리입니다.

제공된 사용자 메시지를 분석하고 관련된 모든 카테고리를 JSON 배열 형식으로 반환하세요.
예: ["exercise", "diet"], ["food"], ["motivation"]

사용자 메시지가 여러 카테고리에 해당할 수 있으며, 최대 3개까지의 관련 카테고리를 반환하세요.
동시에 여러 주제를 언급한 경우, 관련된 모든 카테고리를 포함해야 합니다.
예를 들어, "운동과 식단 계획을 알려줘"는 ["exercise", "food"]과 같이 분류될 수 있습니다."""

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
    Supervisor 클래스는 LangGraph를 사용하여 다중 에이전트 실행을 관리합니다.
    에이전트 노드를 직접 등록하고 워크플로우를 구성할 수 있습니다.
    """
    
    def __init__(self):
        """빈 그래프로 Supervisor를 초기화합니다."""
        # 메트릭 초기화
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_execution_time": 0,
            "node_usage": {}
        }
        
        # 그래프 생성
        self.graph = StateGraph()
        self.nodes = {}
        self.is_compiled = False
        
        # 대화 내역 관리자 초기화
        self.chat_manager = ChatHistoryManager()
        
        logger.info("Supervisor가 빈 그래프로 초기화되었습니다")
    
    def add_node(self, node_name: str, node_func: Callable):
        """
        그래프에 노드를 추가합니다.
        
        Args:
            node_name: 노드 이름
            node_func: 노드 함수
        """
        if self.is_compiled:
            logger.warning("그래프가 이미 컴파일되어 노드를 추가할 수 없습니다")
            return
            
        # 그래프에 노드 추가
        self.graph.add_node(node_name, node_func)
        
        # 노드 함수 저장
        self.nodes[node_name] = node_func
        
        # 메트릭 업데이트
        self.metrics["node_usage"][node_name] = 0
        
        logger.info(f"노드 추가됨: {node_name}")
    
    def add_edge(self, from_node: str, to_node: str):
        """
        노드 간에 엣지를 추가합니다.
        
        Args:
            from_node: 시작 노드 이름
            to_node: 대상 노드 이름 또는 "END"
        """
        if self.is_compiled:
            logger.warning("그래프가 이미 컴파일되어 엣지를 추가할 수 없습니다")
            return
            
        # 엣지 추가
        if to_node == "END":
            self.graph.add_edge(from_node, END)
        else:
            self.graph.add_edge(from_node, to_node)
        
        logger.info(f"엣지 추가됨: {from_node} -> {to_node}")
    
    def add_conditional_edges(self, from_node: str, condition_func: Callable, destinations: Dict[str, str]):
        """
        노드에서 조건부 엣지를 추가합니다.
        
        Args:
            from_node: 시작 노드 이름
            condition_func: 어떤 엣지를 선택할지 결정하는 함수
            destinations: 조건 결과에서 대상 노드로의 매핑
        """
        if self.is_compiled:
            logger.warning("그래프가 이미 컴파일되어 조건부 엣지를 추가할 수 없습니다")
            return
            
        self.graph.add_conditional_edges(from_node, condition_func, destinations)
        logger.info(f"조건부 엣지 추가됨: {from_node}에서 시작")
    
    def set_entry_point(self, node_name: str):
        """
        그래프의 진입점을 설정합니다.
        
        Args:
            node_name: 진입점 노드 이름
        """
        if self.is_compiled:
            logger.warning("그래프가 이미 컴파일되어 진입점을 설정할 수 없습니다")
            return
            
        self.graph.set_entry_point(node_name)
        logger.info(f"진입점 설정됨: {node_name}")
    
    def compile(self):
        """그래프를 컴파일합니다."""
        if self.is_compiled:
            logger.warning("그래프가 이미 컴파일되었습니다")
            return
            
        if not self.nodes:
            logger.error("빈 그래프는 컴파일할 수 없습니다")
            return
            
        # 그래프 컴파일
        self.workflow = self.graph.compile()
        self.is_compiled = True
        
        logger.info("그래프 컴파일 완료")
    
    async def process_message(
        self, 
        message: str, 
        email: str = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        워크플로우를 통해 사용자 메시지를 처리합니다.
        
        Args:
            message: 사용자 메시지 텍스트
            email: 사용자 이메일
            chat_history: 선택적 대화 내역
            request_id: 선택적 요청 ID (제공되지 않으면 생성됨)
            **kwargs: 초기 상태에 포함할 추가 매개변수
            
        Returns:
            Dict: 워크플로우 실행 결과
        """
        if not self.is_compiled:
            raise ValueError("메시지를 처리하기 전에 그래프를 컴파일해야 합니다")
            
        # 타이밍 시작
        start_time = time.time()
        
        # 제공되지 않은 경우 요청 ID 생성
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        # 대화 내역 로드 또는 초기화
        if chat_history is None:
            if email:
                chat_history = self.chat_manager.load_chat_history(email)
            else:
                chat_history = []
        
        # 요청 시작 로깅
        logger.info(f"[{request_id}] 사용자 메시지 처리 시작: {email or '익명'}")
        
        # 총 요청 증가
        self.metrics["total_requests"] += 1
        
        try:
            # 워크플로우 상태 초기화
            initial_state = {
                "request_id": request_id,
                "message": message,
                "email": email,
                "chat_history": chat_history,
                "start_time": start_time,
                "used_nodes": [],  # 사용된 노드 추적
                **kwargs
            }
            
            # 워크플로우 실행
            result = await self.workflow.ainvoke(initial_state)
            
            # 실행 시간 기록
            execution_time = time.time() - start_time
            
            # 메트릭 업데이트
            self.metrics["successful_requests"] += 1
            self._update_avg_execution_time(execution_time)
            
            # 결과에 추적된 경우 노드 사용량 메트릭 업데이트
            if "used_nodes" in result:
                for node_name in result.get("used_nodes", []):
                    if node_name in self.metrics["node_usage"]:
                        self.metrics["node_usage"][node_name] = self.metrics["node_usage"].get(node_name, 0) + 1
            
            # 결과에 실행 시간 추가
            result["execution_time"] = execution_time
            
            # 성공적인 완료 로깅
            logger.info(f"[{request_id}] 처리 완료: {execution_time:.2f}초")
            
            # 응답이 있는 경우 대화 내역에 사용자 메시지와 응답 추가
            if "response" in result:
                updated_chat_history = chat_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": result["response"]}
                ]
                result["chat_history"] = updated_chat_history
                
                # 이메일이 있는 경우 대화 내역 저장
                if email:
                    self.chat_manager.save_chat_history(email, updated_chat_history)
            
            return result
            
        except Exception as e:
            # 실패 기록
            self.metrics["failed_requests"] += 1
            
            # 오류 로깅
            logger.error(f"[{request_id}] 메시지 처리 중 오류 발생: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 오류 정보 반환
            execution_time = time.time() - start_time
            error_response = "죄송합니다, 메시지를 처리하는 동안 오류가 발생했습니다."
            
            return {
                "request_id": request_id,
                "error": f"메시지 처리 오류: {str(e)}",
                "response": error_response,
                "execution_time": execution_time,
                "chat_history": chat_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": error_response}
                ]
            }
    
    def process_message_sync(
        self, 
        message: str, 
        email: str = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        process_message의 동기식 래퍼.
        
        Args:
            message: 사용자 메시지 텍스트
            email: 사용자 이메일
            chat_history: 선택적 대화 내역
            request_id: 선택적 요청 ID
            **kwargs: 초기 상태에 포함할 추가 매개변수
            
        Returns:
            Dict: 워크플로우 실행 결과
        """
        return asyncio.run(self.process_message(message, email, chat_history, request_id, **kwargs))
    
    def _update_avg_execution_time(self, execution_time: float):
        """평균 실행 시간 메트릭을 업데이트합니다."""
        current_avg = self.metrics["avg_execution_time"]
        successful_requests = self.metrics["successful_requests"]
        
        if successful_requests == 1:
            # 첫 번째 성공적인 요청
            self.metrics["avg_execution_time"] = execution_time
        else:
            # 이동 평균 업데이트
            self.metrics["avg_execution_time"] = (
                current_avg * (successful_requests - 1) + execution_time
            ) / successful_requests
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        수퍼바이저의 실행 메트릭을 가져옵니다.
        
        Returns:
            Dict: 요청 및 노드 사용량에 대한 메트릭
        """
        return self.metrics

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
        if hasattr(state, 'response') and state.response:
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
            "response": state.response if hasattr(state, 'response') else "",
            "response_type": state.response_type if hasattr(state, 'response_type') else "text",
            "categories": state.categories if hasattr(state, 'categories') else [],
            "selected_agents": state.selected_agents if hasattr(state, 'selected_agents') else [],
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