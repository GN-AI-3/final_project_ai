"""
Supervisor 모듈 - 모듈화된 컴포넌트를 통합하여 일관된 인터페이스를 제공
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
from supervisor_modules.utils.context_builder import build_agent_context
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

        # API 키 환경 변수 설정
        if hasattr(model, "openai_api_key"):
            api_key = model.openai_api_key
            if hasattr(api_key, "get_secret_value"):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key

        # 에이전트 초기화 및 등록
        from agents import (
            ExerciseAgent,
            FoodAgent,
            ScheduleAgent,
            GeneralAgent,
            MotivationAgent,
        )

        self.agents = {
            "exercise": ExerciseAgent(model),
            "food": FoodAgent(model),
            "schedule": ScheduleAgent(model),
            "motivation": MotivationAgent(model),
            "general": GeneralAgent(model),
        }

        for agent_type, agent_instance in self.agents.items():
            register_agent(agent_type, agent_instance)
            logger.info(f"에이전트 '{agent_type}' 등록 완료")

    async def process(
        self,
        message: str,
        member_id: Optional[str] = None,
        trainer_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        user_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        1) build_agent_context  -> context_info 생성
        2) classify_message      -> 카테고리 결정
        3) 해당 에이전트 실행    -> 최종 응답 반환
        """
        request_id = str(uuid.uuid4())
        try:
            # 0) 사용자 정보
            if not user_type:
                user_type = "member" if member_id else "trainer"
            user_id = member_id or trainer_id
            logger.info(
                f"[{request_id}] 처리 시작 - 메시지: '{message[:50]}...', {user_type}_id: {user_id}"
            )

            # 대화 내역 조회
            if not chat_history and user_id:
                try:
                    chat_history = chat_history_manager.get_recent_messages(user_id, 10)
                    logger.info(
                        f"[{request_id}] 대화 내역 조회 완료 - {len(chat_history)}개"
                    )
                except Exception as e:
                    logger.warning(f"[{request_id}] 대화 내역 조회 실패: {e}")
                    chat_history = []
            elif not chat_history:
                chat_history = []

            # 1) 문맥 정보 생성
            logger.info(f"[{request_id}] (1) 문맥 정보 생성 시작")
            context_info = await build_agent_context(
                message=message, 
                chat_history=chat_history,
                request_id=request_id
            )
            logger.info(f"[{request_id}] (1) 문맥 정보 생성 완료: {len(context_info)}")

            # context_summary 추출
            try:
                context_data = json.loads(context_info)
                agent_context = context_data.get("context_summary", "문맥 정보 없음")
            except Exception:
                logger.warning(f"[{request_id}] context_info JSON 파싱 실패")
                agent_context = "문맥 정보 파싱 실패"

            # 2) 메시지 분류
            logger.info(f"[{request_id}] (2) 카테고리 분류 시작")
            categories, metadata = await classify_message(
                message=message, context_info=context_info
            )
            logger.info(f"[{request_id}] (2) 분류 결과: {categories}")
            category = categories[0] if categories else "general"

            # 3) 에이전트 호출
            logger.info(f"[{request_id}] (3) 에이전트 '{category}' 실행")
            agent = self.agents.get(category, self.agents["general"])

            payload_message = context_info  # ★ 변경: message 자리에 context_info 사용

            try:
                if category == "general":
                    result = await agent.process(
                        message=message,
                        context_info=context_info,
                        chat_history=chat_history,
                    )
                elif category == "schedule":
                    result = await agent.process(
                        message=payload_message, chat_history=chat_history
                    )
                elif category in ["exercise", "motivation", "food"]:
                    result = await agent.process(
                        message=payload_message,
                        email=user_id,
                        chat_history=chat_history,
                    )
                else:
                    result = await agent.process(
                        message=payload_message,
                        agent_context=agent_context,
                        chat_history=chat_history,
                    )
                logger.info(
                    f"[{request_id}] (3) 에이전트 응답: '{result.get('response','')[:60]}...'"
                )
            except TypeError as e:
                logger.warning(
                    f"[{request_id}] 에이전트 매개변수 오류: {e} → fallback 호출"
                )
                result = await agent.process(message=payload_message)

            # 4) 대화 내역 저장
            if user_id:
                chat_history_manager.add_chat_entry(user_id, "user", message)
                chat_history_manager.add_chat_entry(
                    user_id,
                    "assistant",
                    result.get("response", ""),
                    additional_data={"agent_type": category, "selected_agents": categories},
                )

            logger.info(f"[{request_id}] 메시지 처리 완료")
            return {
                "type": result.get("type", category),
                "response": result.get("response", ""),
                "selected_agents": categories,
                "user_type": user_type,
                "execution_time": metadata.get("classification_time", 0),
            }

        except Exception as e:
            logger.error(f"[{request_id}] Supervisor 처리 오류: {e}")
            logger.error(traceback.format_exc())
            return {
                "type": "error",
                "response": f"죄송합니다. 요청을 처리하는 중 문제가 발생했습니다: {e}",
            }
