from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.messages import SystemMessage, HumanMessage
from ...base_agent import BaseAgent
import json
import os
import re
import logging

# 중앙화된 프롬프트 임포트
from ..prompts.prompt_templates import (
    UNIFIED_PROMPT, 
    get_unified_prompt_with_goals,
    get_cheer_prompt,
    CHEER_PROMPT,
    get_system_query_response,
    SYSTEM_QUERY_RESPONSE
)

# 도구 임포트
from ..tools.emotion_tools import EmotionDetectionTool
from ..tools.motivation_tools import MotivationResponseTool
from ..tools.db_tools import DBConnectionTool
from ..workflows.workflow import is_cheer_request, is_system_query

# 로깅 설정
logger = logging.getLogger(__name__)

class MotivationAgent(BaseAgent):
    """
    동기부여 에이전트 - 감정 관련 메시지를 분석하고 맞춤형 동기부여 전략을 제공합니다.
    중앙화된 프롬프트 시스템을 사용하여 일관성을 유지합니다.
    도구 기반 아키텍처를 사용하여 감정 분석 및 응답 생성을 자동화합니다.
    """
    def __init__(self, model: ChatOpenAI):
        super().__init__(model)
        self.model = model
        # 통합 감정 분석 및 응답 생성 모델 설정
        self.unified_model = ChatOpenAI(
            model="gpt-3.5-turbo", 
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=1000,
            streaming=True
        )
        # 백업용 모델 - 필요시 사용
        self.backup_emotion_model = ChatOpenAI(
            model="gpt-3.5-turbo", 
            temperature=0.2,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        logger.info("통합 감정 분석 및 응답 생성 에이전트 초기화 완료")
        
    async def process(self, message: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 한 번의 LLM 호출로 감정 분석과 응답을 생성합니다.
        사용자 이메일이 제공된 경우 DB에서 사용자 목표를 가져와 프롬프트에 통합합니다.
        
        Args:
            message (str): 사용자 메시지
            email (Optional[str]): 사용자 이메일 (DB 조회용)
            
        Returns:
            Dict[str, Any]: 동기부여 응답과 관련 정보
        """
        try:
            # 시스템 관련 질문인지 확인 (가장 먼저 체크)
            if is_system_query(message):
                logger.info("시스템 관련 질문 감지, 보안 응답 제공")
                # 시스템 보안 응답 생성
                prompt = ChatPromptTemplate.from_messages([
                    ("system", SYSTEM_QUERY_RESPONSE),
                    ("human", message)
                ])
                formatted_prompt = prompt.format_messages()
                response_message = await self.unified_model.ainvoke(formatted_prompt)
                
                return {
                    "type": "motivation",
                    "emotion": "neutral",
                    "emotion_intensity": 0.0,
                    "response_strategy": "system_security",
                    "response": response_message.content
                }
            
            # 응원 요청인지 확인
            is_cheer = is_cheer_request(message)
            logger.info(f"응원 요청 확인 결과: {is_cheer}")
            
            # 사용자 목표 조회 (이메일이 제공된 경우)
            user_goals = []
            if email:
                logger.info(f"사용자 목표 조회 시작: {email}")
                user_goals = DBConnectionTool.get_user_goals(email)
                logger.info(f"사용자 목표 조회 결과: {user_goals}")
            
            # 한글 목표로 변환
            korean_goals = [DBConnectionTool.translate_goal_to_korean(goal) for goal in user_goals]
            
            # 먼저 감정 분석을 수행
            logger.info("사용자 메시지 감정 분석 시작")
            emotion_data = EmotionDetectionTool.analyze_emotion(message)
            logger.info(f"감정 분석 결과: 감정={emotion_data['emotion']}, 강도={emotion_data['intensity']}")
            
            # 응원 요청이면 응원 프롬프트 사용
            if is_cheer:
                logger.info("응원 요청 감지, 응원 프롬프트 사용")
                prompt = ChatPromptTemplate.from_messages([
                    ("system", CHEER_PROMPT),
                    ("human", f"사용자 감정: {emotion_data['emotion']} (강도: {emotion_data['intensity']})\n\n사용자 메시지: {message}")
                ])
            else:
                # 목표가 있는 경우 목표가 포함된 프롬프트 템플릿 사용, 그렇지 않으면 기본 프롬프트 사용
                if korean_goals:
                    prompt_template = get_unified_prompt_with_goals(korean_goals)
                else:
                    prompt_template = UNIFIED_PROMPT
                    
                # 프롬프트 템플릿 생성
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_template),
                    ("human", f"사용자 감정: {emotion_data['emotion']} (강도: {emotion_data['intensity']})\n\n사용자 메시지: {message}")
                ])
            
            # 프롬프트 포맷팅
            formatted_prompt = prompt.format_messages()
            
            # 응답 생성
            logger.info("동기부여 응답 생성 시작")
            response_message = await self.unified_model.ainvoke(formatted_prompt)
            response_text = response_message.content
            
            # 전략 추출
            strategy = self._extract_strategy(response_text)
            
            # 최종 응답 생성
            final_result = {
                "type": "motivation",
                "emotion": emotion_data["emotion"],
                "emotion_intensity": emotion_data["intensity"],
                "response_strategy": strategy,
                "response": response_text
            }
            
            # 목표 정보 포함 (있는 경우)
            if user_goals:
                final_result["user_goals"] = korean_goals
                
            return final_result
                
        except Exception as e:
            # 예외 처리 - 에러가 발생하면 기본 응답 반환
            logger.error(f"동기부여 에이전트 처리 중 오류: {str(e)}")
            return self._create_fallback_response(message)

    def _extract_strategy(self, text: str) -> str:
        """응답 텍스트에서 전략을 추출하는 시도"""
        strategies = {
            "위로": "emotional_comfort",
            "위안": "emotional_comfort", 
            "공감": "emotional_comfort",
            "동기": "motivation_boost",
            "의욕": "motivation_boost",
            "시작": "motivation_boost",
            "격려": "encouragement",
            "도전": "encouragement",
            "노력": "encouragement",
            "자신감": "confidence_building",
            "믿음": "confidence_building",
            "능력": "confidence_building"
        }
        
        for keyword, strategy in strategies.items():
            if keyword in text[:200]:  # 앞부분 200자 내에서만 검색
                return strategy
        
        # 기본값
        return "motivation_boost"

    def _create_fallback_response(self, message: str) -> Dict[str, Any]:
        """
        오류 발생 시 대체 응답을 생성합니다.
        필요한 경우 별도의 감정 분석을 수행합니다.
        
        Args:
            message (str): 사용자 메시지
            
        Returns:
            Dict[str, Any]: 대체 응답
        """
        try:
            # 감정 분석 시도
            emotion_data = EmotionDetectionTool.analyze_emotion(message)
            emotion = emotion_data.get("emotion", "neutral")
            intensity = emotion_data.get("intensity", 0.5)
        except:
            # 감정 분석도 실패하면 기본값 사용
            emotion = "neutral"
            intensity = 0.5
            
        return {
            "type": "motivation",
            "emotion": emotion,
            "emotion_intensity": intensity,
            "response_strategy": "motivation_boost",
            "response": "현재 당신의 상황을 이해하려 노력하고 있습니다. 어려운 시간을 보내고 계신 것 같은데, 조금씩 나아질 거예요. 지금 당신이 느끼는 감정은 자연스러운 것이니 너무 자책하지 마세요. 제가 몇 가지 조언을 드리겠습니다.\n\n1. 오늘 하루 5분만 스트레칭을 해보세요. 작은 시작이 큰 변화를 만들 수 있습니다.\n\n2. 짧은 산책을 통해 마음을 환기시키는 것도 좋은 방법입니다.\n\n3. 운동 목표를 작고 구체적으로 세워보세요. 달성 가능한 목표가 동기부여에 도움이 됩니다.\n\n4. 자신의 페이스를 존중하고, 작은 성취에도 스스로를 칭찬해주세요."
        } 