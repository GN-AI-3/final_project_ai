"""
LangGraph 기반 파이프라인 모듈
여러 에이전트를 효율적으로 연결하고 메시지와 컨텍스트를 처리하는 그래프 구조
"""

import logging
import traceback
import json
from typing import Dict, List, Any, Optional, Annotated, Sequence
from typing_extensions import TypedDict
import os
from datetime import datetime

# LangGraph 관련 임포트
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, chain
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# ChatHistoryManager 및 Redis 연결 임포트
from chat_history_manager import ChatHistoryManager

# LLM 및 에이전트 임포트
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# -----------------------------
# 상태 스키마 정의
# -----------------------------
class GymGGunState(TypedDict):
    """파이프라인 상태를 나타내는 스키마"""
    # 기본 메시지 및 이메일
    messages: List[Dict[str, Any]]
    email: str
    original_message: str
    
    # 분석 결과
    is_clear: bool
    category: Optional[str]
    
    # 컨텍스트 정보
    user_context: Optional[Dict]
    chat_history: Optional[List]
    inbody_summary: Optional[str]
    diet_log_summary: Optional[str]
    routine_summary: Optional[str]
    
    # 프롬프트 구성 플래그
    prompt_info_flags: Optional[Dict]
    
    # 에이전트 선택 및 실행 결과
    primary_agent: Optional[str]
    secondary_agents: Optional[List[str]]
    agent_params: Optional[Dict]
    
    # 실행 결과
    primary_result: Optional[Dict]
    secondary_results: Optional[List[Dict]]
    combined_result: Optional[Dict]
    
    # 최종 응답
    final_response: Optional[str]
    response_type: Optional[str]
    needs_followup: Optional[bool]
    
    # 실행 정보
    trace: Optional[Dict]
    execution_time: Optional[float]

# -----------------------------
# 1. 초기 분석 노드 (MessageAnalyzer)
# -----------------------------
def message_analyzer(state: GymGGunState, llm=None) -> GymGGunState:
    """사용자 메시지를 분석하여 카테고리 분류 및 의도 파악"""
    try:
        message = state["original_message"]
        logger.info(f"메시지 분석 시작: {message[:50]}...")
        
        # 간단한 키워드 기반 분류기
        keywords = {
            "exercise": ["운동", "웨이트", "근육", "스트레칭", "헬스", "체력", "유산소", "근력", "다이어트"],
            "food": ["식단", "음식", "식사", "영양", "단백질", "영양소", "먹다", "먹을", "섭취"],
            "diet": ["다이어트", "식이요법", "체중", "감량", "칼로리", "체지방", "체중 감량", "식이 조절"],
            "schedule": ["일정", "스케줄", "계획", "루틴", "시간표", "프로그램", "순서", "시간 관리"],
            "motivation": ["동기", "의욕", "노력", "성취", "목표", "꾸준히", "습관", "결심"]
        }
        
        # 간단한 의도 분류
        category = "general"
        for cat, words in keywords.items():
            for word in words:
                if word in message:
                    category = cat
                    break
            if category != "general":
                break
        
        logger.info(f"메시지 분석 결과 - 카테고리: {category}")
        
        # 결과 업데이트
        return {
            **state,
            "is_clear": True,
            "category": category,
            "trace": {
                **(state.get("trace", {})),
                "message_analysis": {
                    "category": category
                }
            }
        }
    except Exception as e:
        logger.error(f"메시지 분석 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "is_clear": False,
            "category": "error",
            "trace": {
                **(state.get("trace", {})),
                "message_analyzer_error": str(e)
            }
        }

# -----------------------------
# 2. 컨텍스트 로더 노드 (ContextLoader)
# -----------------------------
def context_loader(state: GymGGunState) -> GymGGunState:
    """사용자 컨텍스트 정보 및 채팅 기록 로드"""
    try:
        email = state["email"]
        category = state["category"]
        logger.info(f"컨텍스트 로더 시작 - 이메일: {email}, 카테고리: {category}")
        
        # 채팅 기록 로드
        chat_history = []
        try:
            chat_history_manager = ChatHistoryManager()
            messages = chat_history_manager.get_recent_messages(email, limit=10)
            chat_history = messages
            logger.info(f"채팅 기록 로드 완료 - {len(messages)}개 메시지")
        except Exception as e:
            logger.error(f"채팅 기록 로드 오류: {str(e)}")
            # 오류 발생해도 계속 진행
        
        # 사용자 컨텍스트 정보 (실제로는 DB에서 로드할 것)
        user_context = {
            "email": email,
            "last_activity": datetime.now().isoformat(),
            "preferences": {}
        }
        
        # 결과 업데이트
        return {
            **state,
            "chat_history": chat_history,
            "user_context": user_context,
            "inbody_summary": "",  # 실제로는 DB에서 로드
            "diet_log_summary": "",  # 실제로는 DB에서 로드
            "routine_summary": "",  # 실제로는 DB에서 로드
            "trace": {
                **(state.get("trace", {})),
                "context_loader": {
                    "chat_history_count": len(chat_history),
                    "user_context_loaded": True
                }
            }
        }
    except Exception as e:
        logger.error(f"컨텍스트 로드 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "chat_history": [],
            "user_context": {"email": state["email"]},
            "trace": {
                **(state.get("trace", {})),
                "context_loader_error": str(e)
            }
        }

# -----------------------------
# 3. 에이전트 선택 노드 (AgentSelector)
# -----------------------------
def agent_selector(state: GymGGunState) -> GymGGunState:
    """카테고리 기반으로 적절한 에이전트 선택"""
    try:
        category = state["category"]
        logger.info(f"에이전트 선택 - 카테고리: {category}")
        
        # 카테고리 기반 에이전트 매핑
        agent_mapping = {
            "exercise": {
                "primary": "exercise",
                "secondary": ["motivation"]
            },
            "food": {
                "primary": "food",
                "secondary": ["diet"]
            },
            "diet": {
                "primary": "diet",
                "secondary": ["food"]
            },
            "schedule": {
                "primary": "schedule",
                "secondary": ["motivation"]
            },
            "motivation": {
                "primary": "motivation",
                "secondary": []
            },
            "general": {
                "primary": "general",
                "secondary": []
            },
            "error": {
                "primary": "general",
                "secondary": []
            }
        }
        
        # 기본 매핑이 없으면 general 사용
        if category not in agent_mapping:
            category = "general"
        
        # 에이전트 선택
        primary_agent = agent_mapping[category]["primary"]
        secondary_agents = agent_mapping[category]["secondary"]
        
        # 에이전트 파라미터 (필요한 경우)
        agent_params = {}
        
        # 결과 업데이트
        return {
            **state,
            "primary_agent": primary_agent,
            "secondary_agents": secondary_agents,
            "agent_params": agent_params,
            "trace": {
                **(state.get("trace", {})),
                "agent_selection": {
                    "primary": primary_agent,
                    "secondary": secondary_agents
                }
            }
        }
    except Exception as e:
        logger.error(f"에이전트 선택 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "primary_agent": "general",
            "secondary_agents": [],
            "agent_params": {},
            "trace": {
                **(state.get("trace", {})),
                "agent_selector_error": str(e)
            }
        }

# -----------------------------
# 4. 에이전트 실행 노드 (AgentRunner)
# -----------------------------
def agent_runner(state: GymGGunState, agents: Dict = None) -> GymGGunState:
    """선택된 에이전트들을 실행하고 결과를 수집하는 노드"""
    try:
        message = state["original_message"]
        primary_agent_name = state["primary_agent"]
        secondary_agent_names = state["secondary_agents"]
        agent_params = state["agent_params"]
        
        logger.info(f"에이전트 실행 시작 - 주 에이전트: {primary_agent_name}")
        
        # 컨텍스트 정보 준비
        context = {
            "chat_history": state.get("chat_history", []),
            "user_context": state.get("user_context", {}),
            "inbody_summary": state.get("inbody_summary", ""),
            "diet_log_summary": state.get("diet_log_summary", ""),
            "routine_summary": state.get("routine_summary", "")
        }
        
        primary_result = {"error": "에이전트 실행 실패", "success": False}
        secondary_results = []
        
        # 주 에이전트 실행
        if agents and primary_agent_name in agents:
            try:
                agent = agents[primary_agent_name]
                # 에이전트 실행
                logger.info(f"주 에이전트 {primary_agent_name} 실행 중")
                
                # 매개변수 유효성 검사 - email 매개변수 제거 (에이전트가 지원하지 않을 수 있음)
                safe_params = {}
                # 필요한 경우 context 매개변수만 전달
                safe_params["context"] = context
                
                try:
                    result = agent.process(message, **safe_params)
                except TypeError as e:
                    # 매개변수 오류 시 더 적은 매개변수로 재시도
                    if "unexpected keyword argument" in str(e):
                        logger.warning(f"매개변수 오류, 기본 파라미터로 재시도: {str(e)}")
                        result = agent.process(message)
                    else:
                        raise
                
                # 비동기 함수인 경우 await 처리
                if hasattr(result, "__await__"):
                    try:
                        import asyncio
                        # 현재 콘텍스트가 이미 asyncio 이벤트 루프 내부인지 확인
                        try:
                            is_running = asyncio.get_running_loop()
                            logger.info(f"이벤트 루프가 이미 실행 중입니다. 동기적으로 처리합니다.")
                            result = f"비동기 에이전트 응답: {primary_agent_name} 에이전트가 처리 중입니다."
                        except RuntimeError:
                            # 이벤트 루프가 없으면 새로 만들어서 실행
                            logger.info(f"새 이벤트 루프를 생성합니다.")
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            result = loop.run_until_complete(result)
                    except Exception as e:
                        logger.error(f"비동기 함수 처리 중 오류: {str(e)}")
                        result = f"비동기 처리 오류: {str(e)}"
                
                # 결과 형식 정규화
                if isinstance(result, dict):
                    result["success"] = True
                    if "type" not in result:
                        result["type"] = primary_agent_name
                else:
                    result = {
                        "response": str(result),
                        "type": primary_agent_name,
                        "success": True
                    }
                
                primary_result = result
                logger.info(f"주 에이전트 {primary_agent_name} 실행 완료")
            except Exception as e:
                logger.error(f"주 에이전트 {primary_agent_name} 실행 오류: {str(e)}")
                primary_result = {
                    "error": str(e),
                    "type": primary_agent_name,
                    "success": False,
                    "response": f"죄송합니다. {primary_agent_name} 관련 요청을 처리하는 중에 문제가 발생했습니다."
                }
        
        # 보조 에이전트 실행
        for agent_name in secondary_agent_names:
            if agents and agent_name in agents:
                try:
                    agent = agents[agent_name]
                    # 에이전트 실행
                    logger.info(f"보조 에이전트 {agent_name} 실행 중")
                    
                    # 매개변수 유효성 검사 - email 매개변수 제거 (에이전트가 지원하지 않을 수 있음)
                    safe_params = {}
                    # 필요한 경우 context 매개변수만 전달
                    safe_params["context"] = context
                    
                    try:
                        result = agent.process(message, **safe_params)
                    except TypeError as e:
                        # 매개변수 오류 시 더 적은 매개변수로 재시도
                        if "unexpected keyword argument" in str(e):
                            logger.warning(f"매개변수 오류, 기본 파라미터로 재시도: {str(e)}")
                            result = agent.process(message)
                        else:
                            raise
                    
                    # 비동기 함수인 경우 await 처리
                    if hasattr(result, "__await__"):
                        try:
                            import asyncio
                            # 현재 콘텍스트가 이미 asyncio 이벤트 루프 내부인지 확인
                            try:
                                is_running = asyncio.get_running_loop()
                                logger.info(f"이벤트 루프가 이미 실행 중입니다. 동기적으로 처리합니다.")
                                result = f"비동기 에이전트 응답: {agent_name} 에이전트가 처리 중입니다."
                            except RuntimeError:
                                # 이벤트 루프가 없으면 새로 만들어서 실행
                                logger.info(f"새 이벤트 루프를 생성합니다.")
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                result = loop.run_until_complete(result)
                        except Exception as e:
                            logger.error(f"비동기 함수 처리 중 오류: {str(e)}")
                            result = f"비동기 처리 오류: {str(e)}"
                    
                    # 결과 형식 정규화
                    if isinstance(result, dict):
                        result["success"] = True
                        if "type" not in result:
                            result["type"] = agent_name
                    else:
                        result = {
                            "response": str(result),
                            "type": agent_name,
                            "success": True
                        }
                    
                    secondary_results.append({"agent": agent_name, "data": result, "success": True})
                    logger.info(f"보조 에이전트 {agent_name} 실행 완료")
                except Exception as e:
                    logger.error(f"보조 에이전트 {agent_name} 실행 오류: {str(e)}")
                    secondary_results.append({
                        "agent": agent_name,
                        "error": str(e),
                        "success": False
                    })
        
        # 결과 업데이트
        return {
            **state,
            "primary_result": primary_result,
            "secondary_results": secondary_results
        }
    except Exception as e:
        logger.error(f"에이전트 실행 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "primary_result": {
                "error": str(e),
                "success": False,
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
            },
            "secondary_results": [],
            "trace": {
                **(state.get("trace", {})),
                "agent_runner_error": str(e)
            }
        }

# -----------------------------
# 5. 결과 통합 노드 (ResultCombiner)
# -----------------------------
def result_combiner(state: GymGGunState) -> GymGGunState:
    """주 에이전트와 보조 에이전트 결과를 통합"""
    try:
        primary_result = state["primary_result"]
        secondary_results = state["secondary_results"]
        
        logger.info(f"결과 통합 시작 - 주 결과: {primary_result.get('success', False)}, 보조 결과: {len(secondary_results)}개")
        
        # 주 에이전트 응답 추출
        response = primary_result.get("response", "죄송합니다. 응답을 생성할 수 없습니다.")
        response_type = primary_result.get("type", "general")
        
        # 보조 에이전트 응답 통합 (필요한 경우)
        # 여기서는 간단하게 처리하지만, 실제로는 더 복잡한 통합 로직이 필요할 수 있음
        
        # 결과 업데이트
        return {
            **state,
            "combined_result": {
                "response": response,
                "type": response_type,
                "has_secondary_info": len(secondary_results) > 0
            },
            "trace": {
                **(state.get("trace", {})),
                "result_combiner": {
                    "primary_success": primary_result.get("success", False),
                    "secondary_count": len(secondary_results)
                }
            }
        }
    except Exception as e:
        logger.error(f"결과 통합 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "combined_result": {
                "response": "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다.",
                "type": "error",
                "has_secondary_info": False
            },
            "trace": {
                **(state.get("trace", {})),
                "result_combiner_error": str(e)
            }
        }

# -----------------------------
# 6. 최종 응답 생성 노드 (ResponseGenerator)
# -----------------------------
def response_generator(state: GymGGunState) -> GymGGunState:
    """최종 사용자 응답 생성"""
    try:
        combined_result = state["combined_result"]
        
        logger.info(f"응답 생성 시작 - 응답 타입: {combined_result.get('type', 'unknown')}")
        
        # 최종 응답 추출
        final_response = combined_result.get("response", "죄송합니다. 응답을 생성할 수 없습니다.")
        response_type = combined_result.get("type", "general")
        
        # 후속 질문이 필요한지 여부 (향후 구현 예정)
        needs_followup = False
        
        # 결과 업데이트
        return {
            **state,
            "final_response": final_response,
            "response_type": response_type,
            "needs_followup": needs_followup,
            "trace": {
                **(state.get("trace", {})),
                "response_generator": {
                    "response_length": len(final_response),
                    "response_type": response_type
                }
            }
        }
    except Exception as e:
        logger.error(f"응답 생성 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            **state,
            "final_response": "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다.",
            "response_type": "error",
            "needs_followup": False,
            "trace": {
                **(state.get("trace", {})),
                "response_generator_error": str(e)
            }
        }

# -----------------------------
# 워크플로우 생성 함수
# -----------------------------
def create_workflow(agents=None, llm=None):
    """전체 파이프라인 워크플로우 그래프 생성"""
    # 기본 상태 그래프 생성
    workflow = StateGraph(GymGGunState)
    
    # 노드 추가
    workflow.add_node("message_analyzer", lambda state: message_analyzer(state, llm))
    workflow.add_node("context_loader", context_loader)
    workflow.add_node("agent_selector", agent_selector)
    workflow.add_node("agent_runner", lambda state: agent_runner(state, agents))
    workflow.add_node("result_combiner", result_combiner)
    workflow.add_node("response_generator", response_generator)
    
    # 엣지 연결 (워크플로우 정의)
    workflow.add_edge("message_analyzer", "context_loader")
    workflow.add_edge("context_loader", "agent_selector")
    workflow.add_edge("agent_selector", "agent_runner")
    workflow.add_edge("agent_runner", "result_combiner")
    workflow.add_edge("result_combiner", "response_generator")
    workflow.add_edge("response_generator", END)
    
    # 시작 노드 설정
    workflow.set_entry_point("message_analyzer")
    
    # 컴파일된 그래프 반환
    return workflow.compile()

# -----------------------------
# 파이프라인 클래스
# -----------------------------
class LangGraphPipeline:
    """LangGraph 기반 파이프라인"""
    
    def __init__(self, agents=None, llm=None):
        """LangGraphPipeline 초기화"""
        self.agents = agents or {}
        self.llm = llm
        self.graph = create_workflow(agents=self.agents, llm=self.llm)
        self.metrics = {
            "requests_processed": 0,
            "successful_responses": 0,
            "failed_responses": 0,
            "avg_processing_time": 0
        }
    
    def register_agent(self, category: str, agent: Any) -> None:
        """에이전트를 파이프라인에 등록합니다."""
        self.agents[category] = agent
        # 그래프 재생성
        self.graph = create_workflow(agents=self.agents, llm=self.llm)
        logger.info(f"에이전트 등록 완료: {category}")
    
    async def process(self, message: str, email: str = None, **kwargs) -> Dict[str, Any]:
        """
        메시지 처리 파이프라인을 실행합니다.
        
        Args:
            message: 사용자 메시지
            email: 사용자 이메일 (선택사항)
            
        Returns:
            Dict[str, Any]: 처리 결과
        """
        import time
        start_time = time.time()
        logger.info(f"메시지 처리 파이프라인 시작 - 이메일: {email or '익명'}")
        
        try:
            # 초기 상태 구성
            initial_state = {
                "messages": [{"role": "user", "content": message}],
                "email": email or "anonymous@example.com",
                "original_message": message,
                # 나머지 필드는 기본값 None으로 설정됨
            }
            
            # 그래프 실행
            result = self.graph.invoke(initial_state)
            
            # 실행 시간 계산
            execution_time = time.time() - start_time
            
            # 성공 여부 확인
            is_success = "final_response" in result and result["final_response"]
            
            # 메트릭 업데이트
            self.metrics["requests_processed"] += 1
            if is_success:
                self.metrics["successful_responses"] += 1
            else:
                self.metrics["failed_responses"] += 1
            
            # 평균 처리 시간 업데이트
            count = self.metrics["successful_responses"] + self.metrics["failed_responses"]
            self.metrics["avg_processing_time"] = (
                (self.metrics["avg_processing_time"] * (count - 1) + execution_time) / count
            )
            
            # 최종 결과 구성
            response = {
                "response": result.get("final_response", "처리 중 오류가 발생했습니다."),
                "type": result.get("response_type", "general"),
                "pipeline_trace": result.get("trace", {}),
                "execution_time": execution_time
            }
            
            logger.info(f"파이프라인 처리 완료 - 실행 시간: {execution_time:.2f}초")
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"파이프라인 처리 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 메트릭 업데이트
            self.metrics["requests_processed"] += 1
            self.metrics["failed_responses"] += 1
            
            # 오류 응답 반환
            return {
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다.",
                "type": "error",
                "pipeline_trace": {"error": str(e)},
                "execution_time": execution_time
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """파이프라인 메트릭을 반환합니다."""
        return self.metrics 