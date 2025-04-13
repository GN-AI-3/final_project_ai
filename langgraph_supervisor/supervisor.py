import logging
import traceback
import json
import time
import asyncio
import uuid
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

# 에이전트 불러오기
from chat_history_manager import ChatHistoryManager

# 전역 변수
model = None
agents = {}  # "exercise", "food" 등 key로 agent instance 넣기

# === 상태 스키마 정의 ===
class WorkflowStateDict(TypedDict, total=False):
    request_id: str
    message: str
    email: str
    chat_history: List[Dict[str, Any]]
    categories: List[str]
    selected_agents: List[str]
    agent_outputs: Dict[str, Any]
    agent_errors: Dict[str, str]
    response: str
    response_type: str
    error: Optional[str]
    metrics: Dict[str, Any]
    context: Dict[str, Any]
    used_nodes: List[str]

# === SupervisorState 정의 ===
class SupervisorState:
    def __init__(self, message: str = "", email: str = None, chat_history: List[Dict[str, Any]] = None, start_time: float = None, context: Dict[str, Any] = None):
        self.request_id = str(uuid.uuid4())
        self.message = message
        self.email = email
        self.chat_history = chat_history or []
        self.start_time = start_time or time.time()
        self.categories = []
        self.selected_agents = []
        self.agent_outputs = {}
        self.agent_errors = {}
        self.response = ""
        self.response_type = "general"
        self.error = None
        self.metrics = {}
        self.context = context or {}
        self.used_nodes = []
        self.emotion_score = 0.0  # 감정 점수 (양수: 긍정, 음수: 부정)
        self.emotion_type = None  # 감정 유형 (피로, 슬픔, 화남, 행복 등)
        self.conversation_topics = []  # 대화에서 확인된 주제
        self.recent_mentions = {}  # 최근 언급된 항목들
        self.user_preferences = {}  # 사용자 선호도 
        self.conversation_context = self._extract_context_from_history()
    
    def _extract_context_from_history(self) -> Dict[str, Any]:
        """채팅 기록에서 컨텍스트 정보 추출"""
        if not self.chat_history:
            return {}
            
        context = {
            "recent_topics": [],
            "recent_queries": [],
            "preferences": {}
        }
        
        # 최근 5개 대화만 분석
        recent_messages = self.chat_history[-10:]
        
        # 사용자 메시지만 추출
        user_messages = [msg["content"] for msg in recent_messages if msg.get("role") == "user"]
        
        # 최근 사용자 쿼리 저장
        context["recent_queries"] = user_messages
        
        # 운동 관련 키워드
        exercise_keywords = ["운동", "헬스", "근력", "유산소", "스트레칭", "요가"]
        food_keywords = ["식단", "음식", "식사", "단백질", "탄수화물", "영양"]
        schedule_keywords = ["일정", "계획", "루틴", "시간"]
        
        # 주제 분석
        for message in user_messages:
            # 운동 관련
            if any(keyword in message for keyword in exercise_keywords):
                if "exercise" not in context["recent_topics"]:
                    context["recent_topics"].append("exercise")
            
            # 식단 관련
            if any(keyword in message for keyword in food_keywords):
                if "food" not in context["recent_topics"]:
                    context["recent_topics"].append("food")
                    
            # 일정 관련
            if any(keyword in message for keyword in schedule_keywords):
                if "schedule" not in context["recent_topics"]:
                    context["recent_topics"].append("schedule")
        
        return context
    
    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> 'SupervisorState':
        state = cls()
        for key, value in state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

# === Supervisor 클래스 ===
class Supervisor:
    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_execution_time": 0,
            "node_usage": {}
        }

        self.chat_manager = ChatHistoryManager()
        
        # Check if any agents are registered
        if not agents:
            logging.warning("경고: 등록된 에이전트가 없습니다. 슈퍼바이저 초기화 전에 등록해주세요.")

        self.graph = StateGraph(WorkflowStateDict)

        # 노드 추가 - 실행 순서대로
        self.graph.add_node("Classify", RunnableLambda(classify_message))
        self.graph.add_node("ContextAnalyzer", RunnableLambda(context_analyzer))  # 컨텍스트 분석 노드 추가
        self.graph.add_node("Router", RunnableLambda(self.route_category_node))
        
        # Register agent nodes
        for agent_name in ["exercise", "food", "schedule", "motivation", "general"]:
            self.graph.add_node(f"{agent_name.capitalize()}Agent", RunnableLambda(self.wrap_agent(agent_name)))
            
        self.graph.add_node("generate_response", RunnableLambda(generate_response))

        # Configure graph connections - 노드 간 에지 설정
        self.graph.set_entry_point("Classify")
        self.graph.add_edge("Classify", "ContextAnalyzer")  # 분류 후 컨텍스트 분석
        self.graph.add_edge("ContextAnalyzer", "Router")    # 컨텍스트 분석 후 라우팅
        self.graph.add_conditional_edges(
            "Router", 
            lambda x: x["__return__"],  # Extract the routing decision from the __return__ key
            {
                "exercise": "ExerciseAgent",
                "food": "FoodAgent",
                "schedule": "ScheduleAgent",
                "motivation": "MotivationAgent",
                "general": "GeneralAgent"
            }
        )
        for agent in ["ExerciseAgent", "FoodAgent", "ScheduleAgent", "MotivationAgent", "GeneralAgent"]:
            self.graph.add_edge(agent, "generate_response")
        self.graph.add_edge("generate_response", END)

        # Compile the graph
        self.workflow = self.graph.compile()
        self.is_compiled = True
        logging.info("슈퍼바이저 워크플로우 초기화 및 컴파일 완료")

    def wrap_agent(self, agent_name: str) -> Callable:
        """
        Wraps an agent in a function that can be used as a node in the graph.
        
        Args:
            agent_name: The name of the agent to wrap
            
        Returns:
            A function that takes a state dict and returns an updated state dict
        """
        async def agent_fn(state: Dict[str, Any]) -> Dict[str, Any]:
            state_obj = SupervisorState.from_dict(state)
            # Add user message to chat history if not already there
            if state_obj.chat_history and state_obj.message and (
                len(state_obj.chat_history) == 0 or
                state_obj.chat_history[-1].get("role") != "user" or
                state_obj.chat_history[-1].get("content") != state_obj.message
            ):
                state_obj.chat_history.append({
                    "role": "user",
                    "content": state_obj.message
                })
                
            # Process with agent if available
            if agent_name in agents and agents[agent_name] is not None:
                try:
                    # Log agent processing
                    logging.info(f"[{state_obj.request_id}] {agent_name.capitalize()}Agent 처리 시작")
                    start_time = time.time()
                    
                    # Process the message with the agent
                    result = await agents[agent_name].process(
                        message=state_obj.message,
                        chat_history=state_obj.chat_history
                    )
                    
                    # Record metrics
                    execution_time = time.time() - start_time
                    state_obj.metrics[f"{agent_name}_time"] = execution_time
                    logging.info(f"[{state_obj.request_id}] {agent_name.capitalize()}Agent 처리 완료 (소요시간: {execution_time:.2f}초)")
                    
                    # Store the result
                    state_obj.agent_outputs[agent_name] = result
                except Exception as e:
                    # Log and store the error
                    error_msg = str(e)
                    trace = traceback.format_exc()
                    logging.error(f"[{state_obj.request_id}] {agent_name.capitalize()}Agent 처리 중 오류 발생: {error_msg}\n{trace}")
                    state_obj.agent_errors[agent_name] = error_msg
            else:
                error_msg = f"Agent '{agent_name}' not found or not initialized"
                logging.warning(f"[{state_obj.request_id}] {error_msg}")
                state_obj.agent_errors[agent_name] = error_msg
                
            # Mark this node as used
            state_obj.used_nodes.append(f"{agent_name.capitalize()}Agent")
            return state_obj.to_dict()
        return agent_fn

    def route_category_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines which agent to route to based on categories.
        Returns a dict containing state and a string for the conditional edge.
        """
        state_obj = SupervisorState.from_dict(state)
        categories = state_obj.categories
        state_obj.used_nodes.append("Router")
        
        # Also set selected_agents for API compatibility
        state_obj.selected_agents = categories[:]
        
        # Convert to dict and return the routing decision as a string
        result = state_obj.to_dict()
        return {
            **result,  # Return the full state
            "__return__": categories[0] if categories else "general"  # Special key for the conditional edge
        }

    async def process_message(
        self, 
        message: str, 
        user_id: Optional[str] = None,
        email: Optional[str] = None, 
        chat_history: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the workflow.
        
        Args:
            message: User message text
            user_id: User identifier (will be used as email if email not provided)
            email: User email (deprecated, use user_id instead)
            chat_history: Optional chat history
            request_id: Optional request ID for tracking
            
        Returns:
            Dict: Results of the workflow execution
        """
        if not self.is_compiled:
            raise ValueError("그래프가 컴파일되지 않았습니다.")

        # For backward compatibility, map user_id to email if email not provided
        email_to_use = email or user_id
        
        # Get chat history if not provided
        chat_history = chat_history or (self.chat_manager.load_chat_history(email_to_use) if email_to_use else [])

        # Create initial state
        initial_state = SupervisorState(
            message=message,
            email=email_to_use,
            chat_history=chat_history
        ).to_dict()
        
        # Set request_id if provided
        if request_id:
            initial_state["request_id"] = request_id

        # Execute workflow
        result = await self.workflow.ainvoke(initial_state)

        # Save chat history if email is provided
        if email_to_use:
            await self.chat_manager.save_chat_history(email_to_use, result.get("chat_history", []))

        return result

    def register_agent(self, agent_type: str, agent_instance: Any) -> None:
        """
        Register an agent instance with the supervisor.
        
        Args:
            agent_type: The type of agent (e.g., "exercise", "food")
            agent_instance: The agent instance to register
        """
        global agents
        if agent_type not in ["exercise", "food", "schedule", "motivation", "general"]:
            logging.warning(f"Warning: '{agent_type}' is not a standard agent type. This agent may not be used by the router.")
            
        agents[agent_type] = agent_instance
        logging.info(f"Agent '{agent_type}' registered with the supervisor.")
        
        # Force recompilation if needed
        if self.is_compiled:
            logging.info("Agents updated. Recompiling workflow graph...")
            self.workflow = self.graph.compile()
            logging.info("Workflow graph recompiled successfully.")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for the supervisor
        
        Returns:
            Dict[str, Any]: Current metrics
        """
        # 기본 메트릭
        metrics = self.metrics.copy()
        
        # 노드 사용량 메트릭 계산
        node_usage = {}
        agent_metrics = {}
        
        # 에이전트 종류별 등록 확인
        for agent_type, agent in agents.items():
            if agent is not None:
                agent_metrics[agent_type] = {
                    "status": "active"
                }
        
        metrics["agents"] = agent_metrics
        return metrics

# === 노드용 외부 함수들 ===
def analyze_emotion(message: str, chat_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    감정 분석 및 대화 맥락 고려
    
    Args:
        message: 현재 메시지
        chat_history: 대화 내역 (선택 사항)
        
    Returns:
        Dict with emotion_type, emotion_score and context_info
    """
    # 감정 분석에 필요한 키워드 사전
    negative_words = {
        "피곤해": ("피로", -0.6), "피곤하다": ("피로", -0.6), "지쳤어": ("피로", -0.7), "지치다": ("피로", -0.7),
        "힘들어": ("어려움", -0.8), "힘들다": ("어려움", -0.8), 
        "슬퍼": ("슬픔", -0.8), "슬프다": ("슬픔", -0.8), "우울해": ("우울", -0.9), "우울하다": ("우울", -0.9),
        "화가나": ("화남", -0.7), "화났어": ("화남", -0.7), "짜증나": ("화남", -0.6), "짜증난다": ("화남", -0.6),
        "걱정": ("불안", -0.6), "스트레스": ("불안", -0.7), "불안해": ("불안", -0.7), "불안하다": ("불안", -0.7),
        "못하겠어": ("포기", -0.8), "포기": ("포기", -0.9), "하기싫어": ("의욕저하", -0.7), "귀찮아": ("의욕저하", -0.5),
        "자신감": ("자신감", -0.1), "자존감": ("자존감", -0.1),  # 중립적 단어로 context에 따라 다름
        "못해": ("자신감 부족", -0.7), "안됨": ("좌절", -0.6), "싫어": ("거부", -0.6), "싫다": ("거부", -0.6),
        "지루해": ("지루함", -0.5), "재미없어": ("지루함", -0.5), "관심없어": ("무관심", -0.5)
    }
    
    positive_words = {
        "행복해": ("행복", 0.9), "행복하다": ("행복", 0.9), "기쁘다": ("기쁨", 0.8), "기뻐": ("기쁨", 0.8),
        "좋아": ("호감", 0.7), "좋다": ("호감", 0.7), "즐겁다": ("즐거움", 0.8), "즐거워": ("즐거움", 0.8),
        "힘내": ("격려", 0.6), "할 수 있어": ("자신감", 0.7), "잘 될거야": ("희망", 0.7), "감사": ("감사", 0.8),
        "멋져": ("칭찬", 0.7), "잘했어": ("칭찬", 0.7), "굿": ("칭찬", 0.6), "최고": ("열광", 0.8),
        "신나": ("흥분", 0.8), "기대": ("기대", 0.7), "희망": ("희망", 0.7), "설레": ("기대", 0.7)
    }
    
    # 맥락 분석 결과
    context_info = {
        "has_previous_history": bool(chat_history and len(chat_history) > 0),
        "recent_emotion_mentions": [],
        "recurring_topics": []
    }
    
    # 이전 대화에서 감정 언급 확인 (최근 3개만)
    if chat_history:
        recent_messages = chat_history[-3:] if len(chat_history) >= 3 else chat_history
        for msg in recent_messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                # 이전 메시지에서 감정 단어 확인
                for word in negative_words.keys():
                    if word in user_msg and word not in context_info["recent_emotion_mentions"]:
                        context_info["recent_emotion_mentions"].append(word)
                for word in positive_words.keys():
                    if word in user_msg and word not in context_info["recent_emotion_mentions"]:
                        context_info["recent_emotion_mentions"].append(word)
    
    # 감정과 점수 초기화
    emotion_type = "중립"
    emotion_score = 0.0
    
    # 부정적 단어 검사
    for word, (emotion, score) in negative_words.items():
        if word in message:
            emotion_type = emotion
            emotion_score = min(emotion_score, score)  # 가장 낮은 점수 사용
    
    # 긍정적 단어 검사 (부정적 단어가 없을 경우)
    if emotion_score == 0.0:
        for word, (emotion, score) in positive_words.items():
            if word in message:
                emotion_type = emotion
                emotion_score = max(emotion_score, score)  # 가장 높은 점수 사용
    
    # 맥락에 따른 감정 점수 조정
    # 예: 같은 부정적 감정이 반복되면 더 심각하게 처리
    if context_info["recent_emotion_mentions"] and emotion_score < 0:
        # 연속적인 부정 감정 표현이면 더 낮은 점수 (더 부정적)
        emotion_score -= 0.1
    
    return {
        "emotion_type": emotion_type,
        "emotion_score": emotion_score,
        "context_info": context_info
    }

def analyze_conversation_context(message: str, chat_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    대화 이력을 분석하여 맥락 정보를 추출합니다.
    
    Args:
        message: 현재 사용자 메시지
        chat_history: 이전 대화 이력
        
    Returns:
        Dict: 맥락 정보를 담은 사전
    """
    # 맥락 정보 초기화
    context = {
        "mentioned_topics": [],
        "user_preferences": {},
        "previous_entities": {},
        "reference_messages": [],
        "conversation_flow": "new_topic"  # new_topic, follow_up, topic_change
    }
    
    # 빈 대화 이력이면 초기화된 컨텍스트 반환
    if not chat_history or len(chat_history) < 2:
        return context
    
    # 대화 이력에서 최근 몇 개 메시지만 분석 (너무 오래된 것은 제외)
    recent_history = chat_history[-6:]  # 최대 3번의 턴으로 제한 (user-assistant 쌍)
    
    # 사용자 언급 토픽 및 엔티티 추출
    mentioned_topics = set()
    user_preferences = {}
    entities = {}
    
    # 키워드 기반의 간단한 토픽 탐지
    topic_keywords = {
        "운동": ["운동", "헬스", "체력", "근육", "스트레칭", "유산소", "무산소", "헬스장", "PT", "수영"],
        "식단": ["식단", "음식", "식사", "영양", "칼로리", "단백질", "탄수화물", "지방", "비타민", "먹다", "마시다"],
        "일정": ["일정", "스케줄", "계획", "시간", "일자", "날짜", "요일", "약속", "미팅", "언제", "하루"],
        "감정": ["기분", "감정", "느낌", "행복", "슬픔", "화남", "스트레스", "우울", "불안", "걱정", "지치다"]
    }
    
    # 참조 대상 될 수 있는 용어들 (옷, 음식, 운동 등)
    reference_categories = {
        "의류": ["옷", "바지", "셔츠", "상의", "하의", "신발", "양말", "모자", "코트", "패딩", "겉옷", "속옷", "입다"],
        "음식": ["음식", "밥", "반찬", "사과", "바나나", "고기", "채소", "과일", "야채", "식사", "먹다"],
        "장소": ["집", "회사", "학교", "헬스장", "공원", "카페", "식당", "매장", "가게", "쇼핑몰", "영화관", "가다"]
    }
    
    # 이전 대화에서 언급된 내용 추출
    for i, msg in enumerate(recent_history):
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            
            # 토픽 키워드 매칭
            for topic, keywords in topic_keywords.items():
                if any(kw in content for kw in keywords):
                    mentioned_topics.add(topic)
            
            # 참조 가능한 엔티티 추출
            for category, ref_words in reference_categories.items():
                for word in ref_words:
                    if word in content:
                        # 단순히 단어 등장 여부가 아닌, 문맥을 파악하는 로직 필요
                        # 여기서는 간단히 문장에서 해당 키워드 앞뒤 내용 추출
                        start_idx = max(0, content.find(word) - 10)
                        end_idx = min(len(content), content.find(word) + len(word) + 10)
                        context_snippet = content[start_idx:end_idx]
                        
                        if category not in entities:
                            entities[category] = []
                        
                        entities[category].append({
                            "word": word,
                            "context": context_snippet,
                            "message_idx": i
                        })
    
    # 현재 메시지가 이전 대화와 연결되는지 확인
    if len(recent_history) >= 2:
        last_user_msg = ""
        last_assistant_msg = ""
        
        for msg in reversed(recent_history):
            if msg.get("role") == "user" and not last_user_msg:
                last_user_msg = msg.get("content", "").lower()
            elif msg.get("role") == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg.get("content", "").lower()
            
            if last_user_msg and last_assistant_msg:
                break
        
        # 현재 메시지에 이전 대화 내용을 참조하는 표현이 있는지 확인
        reference_indicators = [
            "그것", "그거", "이것", "저것", "그", "이", "저", 
            "그런", "이런", "저런", "그 것", "이 것", "저 것",
            "그 이야기", "방금", "아까", "이전", "전에", "했", "됐", "했던",
            "거기", "그곳", "여기", "어디", "어떤", "무슨", "어떻게", "왜"
        ]
        
        current_msg = message.lower()
        has_reference = any(indicator in current_msg for indicator in reference_indicators)
        
        # 이전 대화와 현재 대화의 토픽이 같은지 확인
        current_topics = set()
        for topic, keywords in topic_keywords.items():
            if any(kw in current_msg for kw in keywords):
                current_topics.add(topic)
        
        # 대화 흐름 분석
        if has_reference:
            context["conversation_flow"] = "follow_up"
            # 참조 대상이 될 수 있는 이전 메시지 저장
            context["reference_messages"] = [
                {"role": "user", "content": last_user_msg},
                {"role": "assistant", "content": last_assistant_msg}
            ]
        elif current_topics and mentioned_topics and current_topics != mentioned_topics:
            context["conversation_flow"] = "topic_change"
        else:
            context["conversation_flow"] = "new_topic"
    
    # 결과 업데이트
    context["mentioned_topics"] = list(mentioned_topics)
    context["previous_entities"] = entities
    
    return context

def classify_message(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 메시지를 분류하고 감정 분석과 함께 처리합니다.
    대화 맥락 정보도 함께 고려합니다.
    """
    state_obj = SupervisorState.from_dict(state)
    msg = state_obj.message
    
    # 감정 분석 수행 (대화 기록 포함)
    emotion_result = analyze_emotion(msg, state_obj.chat_history)
    state_obj.emotion_type = emotion_result["emotion_type"]
    state_obj.emotion_score = emotion_result["emotion_score"]
    
    # 로깅
    logging.info(f"[{state_obj.request_id}] 감정 분석: {state_obj.emotion_type}({state_obj.emotion_score:.2f})")
    
    # 키워드 기반 분류 (대화 맥락 정보 고려)
    if state_obj.emotion_score < -0.4:
        # 부정적 감정이 강하면 동기부여 에이전트로 라우팅 우선
        state_obj.categories = ["motivation"]
        logging.info(f"[{state_obj.request_id}] 부정적 감정 감지: {state_obj.emotion_type} -> motivation 에이전트로 라우팅")
    
    # 이전 단계에서 카테고리가 지정되지 않았으면 키워드 기반 분류 수행
    if not state_obj.categories:
        # 운동 관련 키워드
        exercise_keywords = ["운동", "헬스", "근력", "유산소", "스트레칭", "요가", "피트니스", 
                             "달리기", "걷기", "수영", "자세", "스쿼트", "푸쉬업", "덤벨", "바벨", 
                             "기구", "트레이닝"]
        
        # 식단 관련 키워드
        food_keywords = ["식단", "음식", "식사", "단백질", "탄수화물", "영양", "칼로리", "비타민",
                         "다이어트", "체중", "살", "체지방", "식이", "먹다", "먹는", "요리",
                         "채소", "과일", "고기", "건강식"]
        
        # 일정 관련 키워드
        schedule_keywords = ["일정", "계획", "루틴", "시간", "스케줄", "월요일", "화요일", "수요일",
                              "목요일", "금요일", "토요일", "일요일", "아침", "점심", "저녁",
                              "주간", "월간", "기간", "언제", "시간표"]
        
        # 동기부여 관련 키워드
        motivation_keywords = ["동기", "의욕", "도움", "격려", "응원", "힘내", "할 수 있", "포기",
                              "자신감", "한계", "극복", "도전", "목표", "성취", "성공", "실패"]
        
        # 키워드 매칭
        if any(keyword in msg for keyword in exercise_keywords):
            state_obj.categories = ["exercise"]
        elif any(keyword in msg for keyword in food_keywords):
            state_obj.categories = ["food"]
        elif any(keyword in msg for keyword in schedule_keywords):
            state_obj.categories = ["schedule"]
        elif any(keyword in msg for keyword in motivation_keywords):
            state_obj.categories = ["motivation"]
        else:
            state_obj.categories = ["general"]
    
    state_obj.used_nodes.append("Classify")
    return state_obj.to_dict()

def generate_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a final response based on agent outputs"""
    state_obj = SupervisorState.from_dict(state)
    
    # Find the agent output to use as response
    outputs = state_obj.agent_outputs
    if outputs:
        # Get the first category's output
        agent_name = state_obj.categories[0] if state_obj.categories else "general"
        if agent_name in outputs:
            response_data = outputs[agent_name]
            # Handle dictionary responses - extract the actual response string
            if isinstance(response_data, dict):
                # Extract response text from dictionary
                if "response" in response_data:
                    state_obj.response = response_data["response"]
                elif "content" in response_data:
                    state_obj.response = response_data["content"]
                else:
                    # If no "response" key, convert the entire dict to string
                    state_obj.response = str(response_data)
            else:
                # String responses
                state_obj.response = response_data
        else:
            # Fallback to any available output
            response_data = list(outputs.values())[0]
            # Handle dictionary responses
            if isinstance(response_data, dict):
                if "response" in response_data:
                    state_obj.response = response_data["response"]
                elif "content" in response_data:
                    state_obj.response = response_data["content"]
                else:
                    state_obj.response = str(response_data)
            else:
                state_obj.response = response_data
    else:
        # No agent outputs available, check for errors
        if state_obj.agent_errors:
            error_msg = list(state_obj.agent_errors.values())[0]
            state_obj.response = f"죄송합니다. 요청을 처리하는 중 오류가 발생했습니다: {error_msg}"
        else:
            # 대화 맥락 기반 응답 생성
            conversation_context = state_obj.conversation_context
            
            # 참조 표현이 있으면 이전 대화 참조
            if conversation_context.get("conversation_flow") == "follow_up":
                reference_msgs = conversation_context.get("reference_messages", [])
                prev_entities = conversation_context.get("previous_entities", {})
                
                # 의류 참조가 있는 경우
                if "의류" in prev_entities:
                    clothing_items = [entity["word"] for entity in prev_entities["의류"]]
                    clothing_str = ", ".join(clothing_items)
                    state_obj.response = f"네, 이전에 언급하신 {clothing_str}에 대해 더 알고 싶으신가요?"
                
                # 음식 참조가 있는 경우
                elif "음식" in prev_entities:
                    food_items = [entity["word"] for entity in prev_entities["음식"]]
                    food_str = ", ".join(food_items)
                    state_obj.response = f"네, 이전에 언급하신 {food_str}에 대해 더 이야기해 볼까요?"
                    
                # 장소 참조가 있는 경우
                elif "장소" in prev_entities:
                    place_items = [entity["word"] for entity in prev_entities["장소"]]
                    place_str = ", ".join(place_items)
                    state_obj.response = f"네, 이전에 언급하신 {place_str}에 대해 더 알고 싶으신가요?"
                
                # 이전 대화 내용이 있지만 특정 엔티티가 없는 경우
                elif reference_msgs:
                    last_user_msg = next((msg["content"] for msg in reference_msgs if msg["role"] == "user"), "")
                    state_obj.response = f"이전에 '{last_user_msg[:20]}...'에 대해 말씀하셨는데, 더 자세히 알고 싶으신가요?"
                    
                else:
                    # 감정 기반 기본 응답
                    if state_obj.emotion_score < -0.6:
                        state_obj.response = f"지금 {state_obj.emotion_type} 상태이신 것 같네요. 많이 힘드신가요? 도움이 필요하시면 말씀해주세요."
                    elif state_obj.emotion_score < -0.3:
                        state_obj.response = f"오늘 기분이 좋지 않으신 것 같아요. 무슨 일이 있으신가요?"
                    elif state_obj.emotion_score > 0.6:
                        state_obj.response = "정말 좋은 에너지를 느낄 수 있네요! 오늘 어떤 일이 있으셨나요?"
                    elif state_obj.emotion_score > 0.3:
                        state_obj.response = "기분이 좋아 보이시네요! 무엇을 도와드릴까요?"
                    else:
                        state_obj.response = "죄송합니다. 응답을 생성할 수 없습니다."
            else:
                # 감정 기반 기본 응답
                if state_obj.emotion_score < -0.6:
                    state_obj.response = f"지금 {state_obj.emotion_type} 상태이신 것 같네요. 많이 힘드신가요? 도움이 필요하시면 말씀해주세요."
                elif state_obj.emotion_score < -0.3:
                    state_obj.response = f"오늘 기분이 좋지 않으신 것 같아요. 무슨 일이 있으신가요?"
                elif state_obj.emotion_score > 0.6:
                    state_obj.response = "정말 좋은 에너지를 느낄 수 있네요! 오늘 어떤 일이 있으셨나요?"
                elif state_obj.emotion_score > 0.3:
                    state_obj.response = "기분이 좋아 보이시네요! 무엇을 도와드릴까요?"
                else:
                    state_obj.response = "죄송합니다. 응답을 생성할 수 없습니다."
    
    # 감정 상태가 매우 부정적인데 motivation 에이전트 외 다른 에이전트가 응답했다면 격려 문구 추가
    if state_obj.emotion_score < -0.6 and (not state_obj.categories or state_obj.categories[0] != "motivation"):
        state_obj.response += "\n\n혹시 힘드신 일이 있으시면 언제든 말씀해주세요. 도움을 드리고 싶습니다."
    
    # Update chat history with the response
    state_obj.chat_history.append({
        "role": "assistant",
        "content": state_obj.response,
        "timestamp": datetime.now().isoformat()  # 타임스탬프 추가
    })
    
    state_obj.used_nodes.append("generate_response")
    return state_obj.to_dict()

def context_analyzer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    대화 맥락을 분석하고 카테고리 분류에 활용하는 노드
    """
    state_obj = SupervisorState.from_dict(state)
    
    # 대화 기록 분석
    if state_obj.chat_history:
        # 최근 대화에서 이미 언급된 주제 확인
        topics = state_obj.conversation_context.get("recent_topics", [])
        
        # 이전에 언급된 주제가 있고 현재 메시지가, 이전 대화의 연속선상에 있는 경우
        # (예: "그것 좀 더 자세히 알려줘", "어떻게 시작하면 돼?")
        continuation_phrases = ["그것", "이것", "그거", "이거", "그", "이", "어떻게", "왜", "언제", "누가", "어디서", "무엇", "뭐", "그럼", "더", "또"]
        
        is_continuation = any(phrase in state_obj.message for phrase in continuation_phrases)
        
        if is_continuation and topics:
            # 이전 대화 주제를 유지
            logging.info(f"[{state_obj.request_id}] 대화 맥락 분석: 이전 주제 '{topics[0]}' 유지")
            state_obj.categories = [topics[0]]  # 가장 최근 주제 사용
            state_obj.used_nodes.append("ContextAnalyzer")
            return state_obj.to_dict()
    
    # 이전 대화와 연관성이 없으면 다음 노드로 진행
    state_obj.used_nodes.append("ContextAnalyzer")
    return state_obj.to_dict()
