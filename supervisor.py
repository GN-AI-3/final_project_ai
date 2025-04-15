"""
Supervisor 모듈 - 모듈화된 코드를 통합하여 사용하는 래퍼 모듈
여러 모듈화된 컴포넌트를 통합하여 일관된 인터페이스를 제공합니다.
"""

import logging
import os
import json
import asyncio
import uuid
import re
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
import traceback

# 모듈화된 컴포넌트 임포트
from supervisor_modules.classification.classifier import classify_message
from supervisor_modules.agents_manager.agents_executor import execute_agents, register_agent, process_message
from supervisor_modules.utils.context_builder import build_agent_context, format_context_for_agent
from supervisor_modules.response.response_generator import generate_response, generate_response_with_insights
from supervisor_modules.state.state_manager import SupervisorState
from chat_history_manager import ChatHistoryManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 채팅 내역 관리자 초기화
chat_history_manager = ChatHistoryManager()

class Supervisor:
    def __init__(self, model: ChatOpenAI):
        self.model = model
        
        # 모델 안정성을 위해 API 키 설정
        if hasattr(model, 'openai_api_key'):
            api_key = model.openai_api_key
            # SecretStr 객체인 경우 문자열로 변환
            if hasattr(api_key, 'get_secret_value'):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key
        
        # 에이전트 초기화 및 등록
        from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
        
        # 에이전트 인스턴스 생성
        self.agents = {
            "exercise": ExerciseAgent(model),
            "food": FoodAgent(model),
            "schedule": ScheduleAgent(model),
            "motivation": MotivationAgent(model),
            "general": GeneralAgent(model)
        }
        
        # agents_executor 모듈에 에이전트 등록
        for agent_type, agent_instance in self.agents.items():
            register_agent(agent_type, agent_instance)
            logger.info(f"에이전트 '{agent_type}' 등록 완료")
    
    async def process(self, message: str, member_id: Optional[str] = None, trainer_id: Optional[str] = None, chat_history: Optional[List[Dict[str, Any]]] = None, user_type: Optional[str] = None) -> Dict[str, Any]:
        """
        메시지를 처리하고 적절한 에이전트로 라우팅하여 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            member_id: 회원 식별자 (이메일 등)
            trainer_id: 트레이너 식별자 (이메일 등)
            chat_history: 대화 내역 (없으면 자동으로 조회)
            user_type: 사용자 타입 ("member" 또는 "trainer")
            
        Returns:
            Dict[str, Any]: 처리 결과
        """
        try:
            # 사용자 타입 및 ID 결정 (member 또는 trainer)
            if not user_type:
                user_type = "member" if member_id else "trainer"
            user_id = member_id or trainer_id
            
            request_id = str(uuid.uuid4())
            logger.info(f"[{request_id}] 처리 시작 - 메시지: '{message[:50]}...', {user_type}_id: {user_id}")
            print(f"\n[SUPERVISOR] 처리 시작 - 메시지: '{message[:50]}...', {user_type}_id: {user_id}")
            
            # 사용자 상태 정보 구성
            user_state = {
                "user_type": user_type,
                "user_id": user_id,
                "member_id": member_id,
                "trainer_id": trainer_id
            }
            
            # 감정 단어를 포함하는 메시지는 우선 동기부여 에이전트로 처리
            emotional_keywords = ["힘들", "슬프", "우울", "불안", "좌절", "스트레스", "자신감", "의욕", "무기력"]
            if any(keyword in message.lower() for keyword in emotional_keywords):
                logger.info(f"[{request_id}] 감정 키워드 감지")
                print(f"[SUPERVISOR] 감정 키워드 감지: '{[kw for kw in emotional_keywords if kw in message.lower()]}'")
                
                try:
                    # SupervisorState 초기화
                    state = SupervisorState(
                        request_id=request_id,
                        message=message,
                        email=user_id,
                        categories=["motivation"],
                        selected_agents=["motivation"]
                    )
                    # 사용자 상태 정보 저장
                    state.context.update(user_state)
                    
                    # 대화 내역 조회 및 설정
                    if not chat_history and user_id:
                        try:
                            chat_history = chat_history_manager.get_recent_messages(user_id, 10)
                            logger.info(f"[{request_id}] 대화 내역 조회 완료 - {len(chat_history)}개 메시지")
                            print(f"[SUPERVISOR] 대화 내역 조회 완료 - {len(chat_history)}개 메시지")
                        except Exception as e:
                            logger.warning(f"[{request_id}] 대화 내역 조회 실패: {str(e)}")
                            print(f"[SUPERVISOR] 대화 내역 조회 실패: {str(e)}")
                            
                    state.chat_history = chat_history or []
                    
                    # 문맥 정보 구성 (user_traits는 None으로 전달)
                    context_info = await build_agent_context(
                        message=message,
                        categories=["motivation"],
                        chat_history=state.chat_history,
                        user_traits=None
                    )
                    state.context_info = context_info
                    
                    # 에이전트에 전달할 문맥 정보 포맷팅
                    motivation_context = format_context_for_agent(context_info, "motivation")
                    print(f"[SUPERVISOR] 동기부여 에이전트 문맥 정보: '{motivation_context[:100]}...'")
                    
                    # 에이전트 실행 (사용자 정보 전달)
                    agent_result = await self.agents["motivation"].process(
                        message, 
                        email=user_id,
                        **{user_type + "_id": user_id}  # member_id 또는 trainer_id로 전달
                    )
                    
                    # 에이전트 결과 저장
                    state.agent_results = [{
                        "agent": "motivation",
                        "result": agent_result
                    }]
                    
                    # 응답 생성
                    response = await generate_response(state)
                    
                    # 대화 내역에 추가
                    if user_id:
                        user_message_added = await chat_history_manager.add_chat_entry_async(user_id, "user", message)
                        if not user_message_added:
                            logger.warning(f"[{request_id}] 사용자 메시지 저장 실패 - 사용자: {user_id}")
                        
                        assistant_message_added = await chat_history_manager.add_chat_entry_async(user_id, "assistant", response)
                        if not assistant_message_added:
                            logger.warning(f"[{request_id}] 어시스턴트 메시지 저장 실패 - 사용자: {user_id}")
                    
                    logger.info(f"[{request_id}] 동기부여 에이전트 처리 완료")
                    print(f"[SUPERVISOR] 동기부여 에이전트 응답: '{response[:50]}...'")
                    
                    return {
                        "type": "motivation",
                        "response": response,
                        "user_type": user_type
                    }
                    
                except Exception as e:
                    logger.error(f"[{request_id}] 동기부여 에이전트 오류: {str(e)}")
                    print(f"[SUPERVISOR] 동기부여 에이전트 오류: {str(e)}")
                    # 동기부여 에이전트 오류 시 일반 처리로 진행
            
            # 일반 처리
            context = {
                "request_id": request_id,
                "email": user_id,
                "user_type": user_type,
                "member_id": member_id,
                "trainer_id": trainer_id
            }
            
            # 대화 내역 조회 및 설정
            if not chat_history and user_id:
                try:
                    chat_history = chat_history_manager.get_recent_messages(user_id, 10)
                    context["chat_history"] = chat_history
                    logger.info(f"[{request_id}] 대화 내역 조회 완료 - {len(chat_history)}개 메시지")
                    print(f"[SUPERVISOR] 대화 내역 조회 완료 - {len(chat_history)}개 메시지")
                except Exception as e:
                    logger.warning(f"[{request_id}] 대화 내역 조회 실패: {str(e)}")
                    print(f"[SUPERVISOR] 대화 내역 조회 실패: {str(e)}")
            elif chat_history:
                context["chat_history"] = chat_history
            
            # 직접 분류 및 에이전트 호출로 변경 (process_message 대신)
            # 1. 메시지 분류
            try:
                # 분류 실행
                categories, metadata = await classify_message(message, context)
                print(f"[SUPERVISOR] 분류 결과: {categories}, 메타데이터: {metadata}")
                
                # 후속 질문 관련 정보 추출
                follow_up_detected = metadata.get("follow_up_detected", False)
                previous_agent = metadata.get("previous_agent")
                
                if follow_up_detected and previous_agent:
                    print(f"[SUPERVISOR] 후속 질문 감지: '{message}'")
                    print(f"[SUPERVISOR] 이전 에이전트('{previous_agent}') 재사용")
                
                # 첫 번째 카테고리를 기본으로 사용
                category = categories[0] if categories else "general"
            except Exception as classify_error:
                print(f"[SUPERVISOR] 분류 오류: {str(classify_error)}")
                # 분류 오류 시 기본 카테고리 사용
                category = "general"
                categories = ["general"]
                metadata = {}
            
            # 문맥 정보 구성 (user_traits는 None으로 전달)
            try:
                print(f"[SUPERVISOR] 문맥 정보 구성 시작 (카테고리: {categories})")
                print(f"[SUPERVISOR] 현재 메시지: '{message}'")
                
                # 대화 내역 요약 로깅
                print(f"[SUPERVISOR] 대화 내역 (총 {len(chat_history) if chat_history else 0}개 항목):")
                if chat_history and len(chat_history) > 0:
                    for i, entry in enumerate(chat_history[-3:]):  # 최근 3개만 로깅
                        role = entry.get("role", "")
                        content = entry.get("content", "")[:100] + ("..." if len(entry.get("content", "")) > 100 else "")
                        print(f"[SUPERVISOR]   {i+1}. {role}: {content}")
                else:
                    print(f"[SUPERVISOR]   대화 내역 없음")
                
                context_info = await build_agent_context(
                    message=message,
                    categories=categories,
                    chat_history=chat_history or [],
                    user_traits=None
                )
                
                # 문맥 기반 카테고리 재조정 (숫자 참조의 경우)
                if has_number_reference := any(char.isdigit() for char in message) and any(term in message for term in ["번", "번째", "항목"]):
                    # 숫자 참조가 있는 경우, 문맥 정보에서 해당 카테고리 확인
                    detected_category = None
                    for cat in ["exercise", "food", "schedule", "motivation"]:
                        if cat in context_info and "번 항목" in context_info[cat]:
                            detected_category = cat
                            print(f"[SUPERVISOR] 번호 참조를 통해 카테고리 재조정: {category} -> {detected_category}")
                            
                            # 카테고리 재조정
                            if detected_category != category:
                                category = detected_category
                                categories = [detected_category]
                            break
                
                agent_context = format_context_for_agent(context_info, category)
                print(f"[SUPERVISOR] 문맥 정보 구성 완료: {len(agent_context)} 자")
                print(f"[SUPERVISOR] 문맥 정보 내용: '{agent_context}'")
            except Exception as context_error:
                print(f"[SUPERVISOR] 문맥 정보 구성 오류: {str(context_error)}")
                agent_context = ""
            
            # 2. 에이전트 호출
            try:
                print(f"[SUPERVISOR] 선택된 에이전트: '{category}'")
                agent = self.agents.get(category, self.agents["general"])
                
                # 에이전트 호출 (사용자 정보 전달)
                # email은 기본 호환성을 위해 유지하고, 추가로 member_id 또는 trainer_id 전달
                agent_kwargs = {
                    "email": user_id,
                    "chat_history": chat_history,  # 대화 내역 전달
                    "agent_context": agent_context,  # 문맥 정보 전달
                    **{user_type + "_id": user_id}  # member_id 또는 trainer_id 추가
                }
                
                # 후속 질문인 경우 이전 메시지 정보 추가
                if follow_up_detected and previous_agent:
                    # 메시지에 숫자(번호)가 포함되어 있는지 확인
                    num_match = re.search(r'(\d+)번', message) or re.search(r'(\d+)\s*[\.번]', message)
                    if num_match:
                        item_num = int(num_match.group(1))
                        print(f"[SUPERVISOR] 숫자 감지: {item_num}번 항목")
                        
                        # context_info에서 참조된 항목 확인 (context_builder가 이미 작업함)
                        referenced_item = None
                        
                        # 컨텍스트 정보에서 항목명 확인
                        for cat, content in context_info.items():
                            # 자세한 설명이 필요합니다 형식 확인
                            item_match = re.search(r"'([^']+)'에 대한 자세한", content)
                            if item_match:
                                referenced_item = item_match.group(1)
                                print(f"[SUPERVISOR] 컨텍스트에서 찾은 참조 항목: '{referenced_item}'")
                                break
                                
                        if referenced_item:
                            # 에이전트에 참조 항목 전달
                            agent_kwargs["referenced_item_content"] = referenced_item
                            agent_kwargs["agent_context"] = f"'{referenced_item}'에 대한 자세한 설명이 필요합니다."
                        else:
                            # 참조 항목을 찾지 못한 경우
                            print(f"[SUPERVISOR] 참조 항목을 찾지 못했습니다: {item_num}번")
                            agent_kwargs["referenced_item_number"] = item_num
                
                # 에이전트의 process 함수가 받을 수 있는 매개변수를 확인하고 전달
                try:
                    result = await agent.process(message, **agent_kwargs)
                except TypeError as e:
                    # 매개변수 오류가 발생하면 agent_context 제거 후 시도
                    error_msg = str(e)
                    print(f"[SUPERVISOR] 에이전트 호출 매개변수 오류: {error_msg}")
                    
                    if "agent_context" in error_msg:
                        # agent_context 매개변수만 제거하고 다시 시도
                        agent_kwargs.pop("agent_context", None)
                        print(f"[SUPERVISOR] agent_context 매개변수 제거 후 재시도")
                        try:
                            result = await agent.process(message, **agent_kwargs)
                        except TypeError:
                            # 다른 매개변수도 문제가 있으면 기본 매개변수만 사용
                            print(f"[SUPERVISOR] 다른 매개변수도 문제가 있음. 기본 매개변수만 사용")
                            result = await agent.process(message, email=user_id)
                    else:
                        # 다른 매개변수 오류의 경우 기본 매개변수만 사용
                        print(f"[SUPERVISOR] 기본 매개변수만 사용")
                        result = await agent.process(message, email=user_id)
                
                print(f"[SUPERVISOR] '{category}' 에이전트 응답: '{result.get('response', '')[:50]}...'")
            except Exception as e:
                print(f"[SUPERVISOR] 에이전트 처리 오류 ({category}): {str(e)}")
                logger.error(traceback.format_exc())
                
                # 오류 발생 시 일반 에이전트로 대체
                if category != "general":
                    try:
                        print(f"[SUPERVISOR] 오류 발생, 일반 에이전트로 대체")
                        # 일반 에이전트에도 사용자 정보 전달
                        try:
                            result = await self.agents["general"].process(
                                message, 
                                email=user_id,
                                chat_history=chat_history,
                                agent_context=agent_context,
                                **{user_type + "_id": user_id}
                            )
                        except TypeError as e:
                            error_msg = str(e)
                            print(f"[SUPERVISOR] 일반 에이전트 호출 매개변수 오류: {error_msg}")
                            
                            if "agent_context" in error_msg:
                                # agent_context 매개변수만 제거하고 다시 시도
                                backup_kwargs = {
                                    "email": user_id,
                                    "chat_history": chat_history,
                                    **{user_type + "_id": user_id}
                                }
                                print(f"[SUPERVISOR] 일반 에이전트 agent_context 매개변수 제거 후 재시도")
                                try:
                                    result = await self.agents["general"].process(message, **backup_kwargs)
                                except TypeError:
                                    # 다른 매개변수도 문제가 있으면 기본 매개변수만 사용
                                    print(f"[SUPERVISOR] 일반 에이전트 다른 매개변수도 문제. 기본 매개변수만 사용")
                                    result = await self.agents["general"].process(message, email=user_id)
                            else:
                                # 다른 매개변수 오류의 경우 기본 매개변수만 사용
                                print(f"[SUPERVISOR] 일반 에이전트 기본 매개변수만 사용")
                                result = await self.agents["general"].process(message, email=user_id)
                        print(f"[SUPERVISOR] 일반 에이전트 응답: '{result.get('response', '')[:50]}...'")
                    except Exception as general_error:
                        print(f"[SUPERVISOR] 일반 에이전트도 실패: {str(general_error)}")
                        result = {
                            "type": "general",
                            "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
                        }
                else:
                    result = {
                        "type": "general",
                        "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다."
                    }
            
            # 대화 내역에 추가
            if user_id:
                user_message_added = await chat_history_manager.add_chat_entry_async(user_id, "user", message)
                if not user_message_added:
                    logger.warning(f"[{request_id}] 사용자 메시지 저장 실패 - 사용자: {user_id}")
                
                assistant_message_added = await chat_history_manager.add_chat_entry_async(user_id, "assistant", result.get("response", ""))
                if not assistant_message_added:
                    logger.warning(f"[{request_id}] 어시스턴트 메시지 저장 실패 - 사용자: {user_id}")
            
            logger.info(f"[{request_id}] 메시지 처리 완료")
            print(f"[SUPERVISOR] 메시지 처리 완료 - 응답: '{result.get('response', '')[:50]}...'")
            
            # 응답 형식 변환
            return {
                "type": result.get("type", "general"),
                "response": result.get("response", ""),
                "selected_agents": [category],
                "user_type": user_type,
                "execution_time": metadata.get("classification_time", 0) if 'metadata' in locals() else 0
            }
            
        except Exception as e:
            logger.error(f"처리 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            print(f"[SUPERVISOR] 처리 중 오류: {str(e)}")
            
            return {
                "type": "error",
                "response": f"죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다: {str(e)}"
            } 