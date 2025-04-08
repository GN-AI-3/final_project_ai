from typing import List, Dict, Any

from langchain_core.messages import HumanMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableMap
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser

from tools import get_user_schedule, add_schedule, modify_schedule
from utils.date_manager import DateManager
from utils.prompt_manager import PromptManager


class ScheduleChatbot:
    """스케줄 예약 챗봇 클래스"""
    
    def __init__(self):
        """챗봇 초기화"""
        self._initialize_llm()
        self._initialize_tools()
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

    def _initialize_tools(self) -> None:
        """도구 초기화"""
        self.tools = [get_user_schedule, add_schedule, modify_schedule]
        self.functions = [convert_to_openai_function(t) for t in self.tools]

    def _initialize_prompt(self) -> None:
        """프롬프트 초기화"""
        system_prompt = PromptManager.load_system_prompt()
        formatted_date, _ = DateManager.get_formatted_date()
        system_prompt = (
            f"오늘은 {formatted_date}입니다.\n\n"
            f"{system_prompt}\n\n"
            "스케줄은 오늘 이후의 날짜로만 가능해요."
        )
        self.prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="chat_history"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
            ("human", "{input}")
        ]).partial(system_prompt=system_prompt)

    def _get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """세션 ID에 해당하는 대화 기록 가져오기"""
        if session_id not in self.histories:
            self.histories[session_id] = InMemoryChatMessageHistory()
        return self.histories[session_id]

    def _initialize_agent(self) -> None:
        """에이전트 초기화"""
        base_agent: RunnableMap = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x.get("intermediate_steps", [])
                ),
                "chat_history": lambda x: x.get("chat_history", [])
            }
            | self.prompt
            | self.llm.bind(functions=self.functions)
            | OpenAIFunctionsAgentOutputParser()
        )

        self.agent_executor = AgentExecutor(
            agent=base_agent,
            tools=self.tools,
            verbose=False
        )

    def process_message(self, message: str, session_id: str = "default") -> str:
        """사용자 메시지 처리"""
        try:
            # 대화 기록 가져오기
            history = self._get_history(session_id)
            
            # 대화 기록을 메시지 리스트로 변환
            chat_history = history.messages
            
            # 에이전트 실행
            result = self.agent_executor.invoke({
                "input": message,
                "chat_history": chat_history
            })
            
            # 결과 처리
            if isinstance(result, dict) and "output" in result:
                output = result["output"]
            else:
                output = str(result)
            
            # 대화 기록에 메시지 추가
            history.add_user_message(message)
            history.add_ai_message(output)
            
            return output
                
        except Exception as e:
            return f"죄송해요. 오류가 발생했어요: {str(e)}"


def call_chatbot(messages: List[Dict[str, Any]], session_id: str = "default") -> str:
    """챗봇 호출 함수"""
    try:
        if not hasattr(call_chatbot, "chatbot_instance"):
            call_chatbot.chatbot_instance = ScheduleChatbot()

        chatbot = call_chatbot.chatbot_instance

        last_message = messages[-1]
        if isinstance(last_message, dict):
            message_content = last_message.get("content")
        elif isinstance(last_message, HumanMessage):
            message_content = last_message.content
        else:
            return "죄송해요. 메시지 형식이 올바르지 않아요."

        return chatbot.process_message(message_content, session_id=session_id)

    except Exception as e:
        return "죄송해요. 문제가 발생했어요. 다시 시도해 주시겠어요?"
