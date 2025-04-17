"""
Supervisor 모듈 - 모듈화된 코드를 통합하여 사용하는 래퍼 모듈
여러 모듈화된 컴포넌트를 통합하여 일관된 인터페이스를 제공합니다.
"""

import logging
import os
import json
import uuid
import traceback
from typing import Dict, Any, List, Optional

# LangChain/OpenAI
from langchain_openai import ChatOpenAI

# 모듈화된 컴포넌트 임포트
from supervisor_modules.classification.classifier import classify_message
from supervisor_modules.utils.context_builder import build_agent_context, format_context_for_agent
from supervisor_modules.response.response_generator import generate_response, generate_response_with_insights
from supervisor_modules.state.state_manager import SupervisorState
from chat_history_manager import ChatHistoryManager
from supervisor_modules.agents_manager.agents_executor import register_agent

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
        
        # 에이전트 초기화
        from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
        
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
    
    async def process(
        self, 
        message: str, 
        member_id: Optional[str] = None, 
        trainer_id: Optional[str] = None, 
        chat_history: Optional[List[Dict[str, Any]]] = None, 
        user_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        메시지를 처리하고 적절한 에이전트로 라우팅하여 응답을 생성합니다.
        
        1) build_agent_context -> 전체 문맥 요약 정보(context_info) 생성
        2) classify_message -> context_info + message 기반으로 카테고리 결정
        3) 결정된 카테고리의 에이전트에 메시지 전달 -> 최종 응답 생성
        """
        try:
            # 0) 사용자 식별 및 로그
            if not user_type:
                user_type = "member" if member_id else "trainer"
            user_id = member_id or trainer_id
            
            request_id = str(uuid.uuid4())
            logger.info(f"[{request_id}] 처리 시작 - 메시지: '{message[:50]}...', {user_type}_id: {user_id}")
            
            # 대화 내역이 없으면 DB에서 불러오기
            if not chat_history and user_id:
                try:
                    chat_history = chat_history_manager.get_recent_messages(user_id, 10)
                    logger.info(f"[{request_id}] 대화 내역 조회 완료 - {len(chat_history)}개 메시지")
                except Exception as e:
                    logger.warning(f"[{request_id}] 대화 내역 조회 실패: {str(e)}")
                    chat_history = []
            elif not chat_history:
                chat_history = []
            
            # 1) 문맥 정보 생성 (ContextBuilder)
            logger.info(f"[{request_id}] (1) 문맥 정보 생성 시작")
            context_info = await build_agent_context(
                message=message,
                chat_history=chat_history
            )
            logger.info(f"[{request_id}] (1) 문맥 정보 생성 완료: {len(context_info)} chars")
            
            # JSON 파싱 시도하여 구조 확인
            try:
                context_data = json.loads(context_info)
                logger.debug(f"[{request_id}] 문맥 정보 구조: {list(context_data.keys())}")
            except:
                logger.warning(f"[{request_id}] 문맥 정보 JSON 파싱 실패")
            
            # 2) 메시지 분류 (Classifier) - context_info 활용
            logger.info(f"[{request_id}] (2) 카테고리 분류 시작")
            categories, metadata = await classify_message(
                message=message,
                context_info=context_info
            )
            logger.info(f"[{request_id}] (2) 분류 결과: {categories}")
            
            # 첫 번째 카테고리를 기본으로
            if categories:
                category = categories[0]
            else:
                category = "general"
            
            # 3) 에이전트 호출
            logger.info(f"[{request_id}] (3) 에이전트 '{category}' 실행")
            agent = self.agents.get(category, self.agents["general"])
            
            # build_agent_context에서 이미 요약정보를 만들어뒀으니,
            # 그중 핵심 요약만 agent_context로 넘길 수 있음
            # 예: {"context_summary": "..."} 구조라고 가정
            try:
                context_data = json.loads(context_info)
                agent_context = context_data.get("context_summary", "문맥 정보 없음")
            except:
                logger.warning(f"[{request_id}] 문맥 정보 JSON 파싱 실패")
                agent_context = "문맥 정보 파싱 실패"

            # 에이전트 호출
            # (해당 에이전트가 어떤 인자를 받는지에 따라 조정)
            try:
                if category == "general":
                    result = await agent.process(message, context_info=agent_context, chat_history=chat_history)
                elif category == "schedule":
                    try:
                        # chat_history 파라미터를 지원하는지 확인
                        result = await agent.process(message, chat_history=chat_history)
                    except TypeError:
                        # 지원하지 않으면 기본 호출
                        result = await agent.process(message)
                elif category in ["exercise", "motivation", "food"]:
                    result = await agent.process(message, email=user_id, chat_history=chat_history)
                else:
                    # 기본 패턴 (모두 전달)
                    result = await agent.process(message, agent_context=agent_context, chat_history=chat_history)
                logger.info(f"[{request_id}] (3) 에이전트 응답: '{result.get('response', '')[:60]}...'")
            except TypeError as e:
                # 매개변수 문제 시 fallback
                logger.warning(f"[{request_id}] 에이전트 매개변수 오류: {str(e)} -> fallback to minimal")
                result = await agent.process(message)
            
            # 4) 대화 내역에 추가
            if user_id:
                # 사용자 메시지 저장
                user_message_saved = chat_history_manager.add_chat_entry(user_id, "user", message)
                if not user_message_saved:
                    logger.warning(f"[{request_id}] 사용자 메시지 저장 실패 - {user_id}")
                
                # 에이전트(assistant) 메시지 저장
                additional_data = {
                    "agent_type": category,
                    "selected_agents": categories
                }
                
                # 결과에서 추가 메타데이터가 있다면 저장
                if isinstance(result, dict):
                    # emotion_type이 있으면 저장
                    if "emotion_type" in result:
                        additional_data["emotion_type"] = result["emotion_type"]
                    
                    # 다른 메타데이터가 있으면 추가
                    if "metadata" in result and isinstance(result["metadata"], dict):
                        additional_data.update(result["metadata"])
                
                assistant_message_saved = chat_history_manager.add_chat_entry(
                    user_id, 
                    "assistant",
                    result.get("response", ""),
                    additional_data=additional_data
                )
                if not assistant_message_saved:
                    logger.warning(f"[{request_id}] 어시스턴트 메시지 저장 실패 - {user_id}")
            
            logger.info(f"[{request_id}] 메시지 처리 완료")
            logger.info(f"[{request_id}] 메시지 처리 완료 - 응답: '{result.get('response', '')[:50]}...'")
            
            return {
                "type": result.get("type", category),
                "response": result.get("response", ""),
                "selected_agents": categories,
                "user_type": user_type,
                "execution_time": metadata.get("classification_time", 0)
            }
        
        except Exception as e:
            logger.error(f"Supervisor 처리 오류: {str(e)}")
            logger.error(traceback.format_exc())
            logger.info(f"[{request_id}] 처리 중 오류: {str(e)}")
            return {
                "type": "error",
                "response": f"죄송합니다. 요청을 처리하는 중 문제가 발생했습니다: {str(e)}"
            }
