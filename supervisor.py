from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from agents import ExerciseAgent, FoodAgent, ScheduleAgent, GeneralAgent, MotivationAgent
import os
import openai
import traceback
import logging
from chat_history_manager import ChatHistoryManager

# 로깅 설정
logger = logging.getLogger(__name__)

class Supervisor:
    def __init__(self, model: ChatOpenAI):
        self.model = model
        self.chat_history_manager = ChatHistoryManager()
        
        # 모델 안정성을 위해 직접 API 키 설정
        # SecretStr 타입이면 문자열로 변환
        if hasattr(model, 'openai_api_key'):
            api_key = model.openai_api_key
            # SecretStr 객체인 경우 문자열로 변환
            if hasattr(api_key, 'get_secret_value'):
                api_key = api_key.get_secret_value()
            os.environ["OPENAI_API_KEY"] = api_key
            
        # 직접 OpenAI 클라이언트 초기화
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        self.agents = {
            "exercise": ExerciseAgent(model),
            "food": FoodAgent(model),
            "schedule": ScheduleAgent(model),
            "motivation": MotivationAgent(model),
            "general": GeneralAgent(model)
        }
    
    def get_conversation_context(self, email: str, limit: int = 5) -> str:
        """
        Redis에서 사용자의 이전 대화 내역을 가져와 문맥으로 활용할 수 있는 형식으로 반환
        
        Args:
            email: 사용자 이메일
            limit: 가져올 대화 내역 최대 개수 (기본값: 5)
            
        Returns:
            문맥으로 사용할 수 있는 대화 내역 문자열
        """
        try:
            if not email:
                logger.info("이메일이 제공되지 않아 대화 내역을 조회하지 않습니다.")
                return ""
                
            logger.info(f"Redis에서 대화 내역 조회 - 이메일: {email}, 개수: {limit}")
            messages = self.chat_history_manager.get_recent_messages(email, limit)
            
            if not messages:
                logger.info(f"조회된 대화 내역 없음 - 이메일: {email}")
                return ""
                
            # 대화 내역을 문맥으로 형식화
            context = "이전 대화 내역:\n"
            for i, msg in enumerate(messages):
                role = "사용자" if msg.get("role") == "user" else "AI"
                content = msg.get("content", "")
                # 너무 긴 메시지는 잘라서 표시
                if len(content) > 200:
                    content = content[:200] + "..."
                context += f"{role}: {content}\n"
            
            logger.info(f"대화 내역 조회 완료 - {len(messages)}개 메시지")
            return context
            
        except Exception as e:
            logger.error(f"대화 내역 조회 오류: {str(e)}")
            return ""
        
    async def analyze_message(self, message: str, context: str = "") -> str:
        # LangChain 대신 직접 OpenAI API 호출
        try:
            # 문맥이 있으면 포함하여 분류 요청
            system_content = """다음 카테고리 중 하나로 메시지를 분류해주세요:
            - schedule: PT 일정 조회, 등록, 수정, 취소
            - exercise: PT 일정을 제외한 운동 관련
            - food: 식단, 영양, 음식 등
            - motivation: 감정적 어려움, 동기부여가 필요한 내용, 우울함, 좌절, 불안 등
            - general: 위 카테고리에 속하지 않는 일반적인 대화
            
            응답은 위 카테고리 중 하나만 반환해주세요."""
            
            messages = [{"role": "system", "content": system_content}]
            
            # 문맥이 있으면 추가
            if context:
                messages.append({"role": "user", "content": f"다음은 사용자와의 이전 대화 내역입니다:\n{context}\n\n사용자의 새 메시지를 분류해주세요: {message}"})
            else:
                messages.append({"role": "user", "content": message})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=50
            )
            
            # 응답에서 카테고리 추출
            response_text = response.choices[0].message.content.strip().lower()
            
            # 유효한 카테고리인지 확인
            valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
            if response_text not in valid_categories:
                # 정확히 일치하는 카테고리가 없으면 각 카테고리 키워드 확인
                if "운동" in message or "체육" in message:
                    return "exercise"
                elif "식단" in message or "음식" in message or "영양" in message:
                    return "food"
                elif "일정" in message or "계획" in message or "시간" in message:
                    return "schedule"
                elif "힘들" in message or "슬프" in message or "우울" in message or "불안" in message or "좌절" in message:
                    return "motivation"
                else:
                    return "general"
            
            return response_text
        except Exception as e:
            logger.error(f"메시지 분류 오류: {str(e)}")
            # 오류 발생 시 일반 카테고리로 처리
            return "general"
    
    async def process(self, message: str, member_id: int = None, email: str = None) -> Dict[str, Any]:
        try:
            logger.info(f"메시지 처리 시작 - 이메일: {email or '없음'}")
            
            # Redis에서 이전 대화 내역 가져오기
            context = ""
            if email:
                context = self.get_conversation_context(email)
                if context:
                    logger.info(f"이전 대화 내역 가져옴 - 이메일: {email}")
                else:
                    logger.info(f"이전 대화 내역 없음 - 이메일: {email}")
            
            # 감정 단어를 포함하는 메시지는 우선 동기부여 에이전트로 처리
            emotional_keywords = ["힘들", "슬프", "우울", "불안", "좌절", "스트레스", "자신감", "의욕", "무기력"]
            if any(keyword in message.lower() for keyword in emotional_keywords):
                try:
                    logger.info(f"감정 키워드 감지로 동기부여 에이전트 사용 - 이메일: {email or '없음'}")
                    
                    # 점진적으로 매개변수 축소 시도 - member_id는 제외
                    try:
                        # email과 context 매개변수 전달 시도
                        if email is not None:
                            # context 매개변수를 지원하는지 확인
                            if hasattr(self.agents["motivation"], 'process') and 'context' in self.agents["motivation"].process.__code__.co_varnames:
                                return await self.agents["motivation"].process(message, email=email, context=context)
                            else:
                                return await self.agents["motivation"].process(message, email=email)
                        # 매개변수 없이 시도
                        else:
                            return await self.agents["motivation"].process(message)
                    except TypeError as e:
                        logger.warning(f"동기부여 에이전트 매개변수 오류, 인자 없이 재시도: {str(e)}")
                        return await self.agents["motivation"].process(message)
                except Exception as e:
                    logger.error(f"동기부여 에이전트 오류: {str(e)}")
                    logger.error("동기부여 에이전트 오류로 일반 처리로 전환")
                    # 명시적으로 일반 처리로 진행함을 표시
            
            # 일반 처리 진행
            category = await self.analyze_message(message, context)
            agent = self.agents.get(category, self.agents["general"])
            logger.info(f"메시지 카테고리: {category} - 이메일: {email or '없음'}")
            
            response_data = None
            try:
                # 점진적으로 매개변수 축소 시도 - member_id는 제외
                try:
                    # email과 context 매개변수 전달 시도
                    if email is not None:
                        # context 매개변수를 지원하는지 확인
                        if hasattr(agent, 'process') and 'context' in agent.process.__code__.co_varnames:
                            response_data = await agent.process(message, email=email, context=context)
                        else:
                            response_data = await agent.process(message, email=email)
                    # 매개변수 없이 시도
                    else:
                        response_data = await agent.process(message)
                except TypeError as e:
                    logger.warning(f"{category} 에이전트 매개변수 오류, 인자 없이 재시도: {str(e)}")
                    response_data = await agent.process(message)
                
                # 응답 검증
                if response_data is None:
                    logger.error(f"{category} 에이전트가 None을 반환")
                    response_data = {
                        "type": category,
                        "response": f"죄송합니다. {category} 관련 요청을 처리하는 중에 문제가 발생했습니다."
                    }
                
                return response_data
            except Exception as e:
                print(f"에이전트 처리 오류 ({category}): {str(e)}")
                traceback.print_exc()
                # 오류 발생 시 일반 에이전트로 대체
                if category != "general":
                    try:
                        # 점진적으로 매개변수 축소 시도 - 일반 에이전트, member_id는 제외
                        try:
                            # email과 context 매개변수 전달 시도
                            if email is not None:
                                # context 매개변수를 지원하는지 확인
                                if hasattr(self.agents["general"], 'process') and 'context' in self.agents["general"].process.__code__.co_varnames:
                                    response_data = await self.agents["general"].process(message, email=email, context=context)
                                else:
                                    response_data = await self.agents["general"].process(message, email=email)
                            # 매개변수 없이 시도
                            else:
                                response_data = await self.agents["general"].process(message)
                        except TypeError as e:
                            logger.warning(f"일반 에이전트 매개변수 오류, 인자 없이 재시도: {str(e)}")
                            response_data = await self.agents["general"].process(message)
                        
                        # 응답 검증
                        if response_data is None:
                            logger.error("일반 에이전트가 None을 반환")
                            response_data = {
                                "type": "general",
                                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다른 질문으로 다시 시도해주세요."
                            }
                        
                        return response_data
                    except Exception as e2:
                        logger.error(f"일반 에이전트 대체 중 오류: {str(e2)}")
                
                # 모든 시도가 실패한 경우 기본 응답 반환
                return {
                    "type": "general",
                    "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다른 질문으로 다시 시도해주세요."
                }
        except Exception as e:
            logger.error(f"처리 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "type": "general",
                "response": "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다른 질문으로 다시 시도해주세요."
            } 