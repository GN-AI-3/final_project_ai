from typing import List, Dict, Any, Optional
import json
import base64

try:
    import jwt
    # jwt 패키지가 decode 메서드를 가지고 있는지 확인
    HAS_JWT_DECODE = hasattr(jwt, 'decode')
except ImportError:
    # 패키지 설치 안됨
    HAS_JWT_DECODE = False

from langchain_core.messages import HumanMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableMap
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser

from .tools import get_user_schedule, add_schedule, modify_schedule, get_trainer_schedule, get_member_schedule
from .utils.date_manager import DateManager
from .utils.prompt_manager import PromptManager


class ScheduleChatbot:
    """스케줄 예약 챗봇 클래스"""
    
    def __init__(self, tools: Optional[List] = None):
        """챗봇 초기화
        
        Args:
            tools: 사용할 도구 리스트 (기본값: None)
        """
        self._initialize_llm()
        self._initialize_tools(tools)
        self._initialize_prompt()
        self.histories: Dict[str, InMemoryChatMessageHistory] = {}
        self._initialize_agent()

    def _initialize_llm(self) -> None:
        """LLM 모델 초기화"""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True
        )

    def _initialize_tools(self, tools: Optional[List] = None) -> None:
        """도구 초기화
        
        Args:
            tools: 사용할 도구 리스트 (기본값: None)
        """
        self.tools = tools or [get_user_schedule, add_schedule, modify_schedule, get_trainer_schedule, get_member_schedule]
        self.functions = [convert_to_openai_function(t) for t in self.tools]

    def _initialize_prompt(self) -> None:
        """프롬프트 초기화"""
        system_prompt = PromptManager.load_system_prompt()
        formatted_date, _ = DateManager.get_formatted_date()
        system_prompt = (
            f"오늘은 {formatted_date}입니다.\n\n"
            f"{system_prompt}"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

    def _get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """세션 ID에 해당하는 채팅 기록을 가져옵니다.
        
        Args:
            session_id: 세션 ID
            
        Returns:
            InMemoryChatMessageHistory: 채팅 기록 객체
        """
        if session_id not in self.histories:
            self.histories[session_id] = InMemoryChatMessageHistory()
        return self.histories[session_id]

    def _initialize_agent(self) -> None:
        """에이전트 초기화"""
        self.agent = (
            RunnableMap({
                "input": lambda x: x["input"],
                "chat_history": lambda x: self._get_history(x["session_id"]).messages,
                "agent_scratchpad": lambda x: format_to_openai_function_messages(x["intermediate_steps"])
            })
            | self.prompt
            | self.llm.bind(functions=self.functions)
            | OpenAIFunctionsAgentOutputParser()
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )

    def process_message(self, message: str, session_id: str = "default") -> str:
        """메시지를 처리하고 응답을 생성합니다.
        
        Args:
            message: 사용자 메시지
            session_id: 세션 ID (기본값: "default")
            
        Returns:
            str: 생성된 응답
        """
        try:
            response = self.agent_executor.invoke({
                "input": message,
                "session_id": session_id
            })
            
            return json.dumps({
                "success": True,
                "message": response["output"]
            })
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                return json.dumps({
                    "success": False,
                    "message": "응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."
                })
            return json.dumps({
                "success": False,
                "message": f"오류가 발생했습니다: {error_msg}"
            })


def get_member_id_from_token(token: str) -> int:
    """JWT 토큰에서 member_id를 추출합니다.
    
    Args:
        token (str): JWT 토큰
        
    Returns:
        int: member_id, 추출 실패 시 0
    """
    try:
        if HAS_JWT_DECODE:
            decoded = jwt.decode(token, options={"verify_signature": False})
        else:
            # 수동으로 JWT 디코딩
            token_parts = token.split('.')
            if len(token_parts) >= 2:
                # 패딩 추가
                padded = token_parts[1] + '=' * (4 - len(token_parts[1]) % 4)
                # base64 디코딩 후 JSON 파싱
                decoded = json.loads(base64.b64decode(padded).decode('utf-8'))
            else:
                return 0
        
        return decoded.get("id", 0)
    except Exception:
        return 0

def call_chatbot(messages: List[Dict[str, Any]], token: str = None, session_id: str = "default") -> str:
    """챗봇을 호출하여 응답을 생성합니다.
    
    Args:
        messages: 메시지 리스트
        token: JWT 토큰 (기본값: None)
        session_id: 세션 ID (기본값: "default")
        
    Returns:
        str: 생성된 응답
    """
    # 토큰이 제공된 경우 member_id를 session_id로 사용
    if token:
        member_id = get_member_id_from_token(token)
        if member_id != 0:
            session_id = str(member_id)
            
    chatbot = ScheduleChatbot()
    last_message = messages[-1]
    if isinstance(last_message, dict):
        message_content = last_message.get("content")
    elif hasattr(last_message, "content"):
        message_content = last_message.content
    else:
        return json.dumps({
            "success": False,
            "message": "죄송합니다. 메시지 형식이 올바르지 않습니다."
        })
        
    return chatbot.process_message(message_content, session_id)
