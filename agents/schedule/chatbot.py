from typing import List, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.utils.function_calling import convert_to_openai_function

from tools import get_user_schedule, add_reservation, modify_reservation
from utils.date_manager import DateManager
from utils.prompt_manager import PromptManager

class ScheduleChatbot:
    """일정 관리 채팅봇 클래스"""
    def __init__(self):
        self._initialize_llm()
        self._initialize_tools()
        self._initialize_prompt()
        self._initialize_agent()
        self.chat_history = []
        self.pending_reservation_no = None
    
    def _initialize_llm(self) -> None:
        """LLM을 초기화합니다."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True
        )
    
    def _initialize_tools(self) -> None:
        """사용할 도구들을 초기화합니다."""
        self.tools = [get_user_schedule, add_reservation, modify_reservation]
        self.functions = [convert_to_openai_function(t) for t in self.tools]
    
    def _initialize_prompt(self) -> None:
        """프롬프트를 초기화합니다."""
        system_prompt = PromptManager.load_system_prompt()
        formatted_date, _ = DateManager.get_formatted_date()
        system_prompt = f"오늘은 {formatted_date}입니다.\n\n{system_prompt}\n\n 예약은 오늘 이후의 날짜로만 가능해요."
        self.prompt = PromptManager.create_prompt_template(system_prompt)
    
    def _initialize_agent(self) -> None:
        """에이전트를 초기화합니다."""
        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
                "chat_history": lambda x: x["chat_history"],
            }
            | self.prompt
            | self.llm.bind(functions=self.functions)
            | OpenAIFunctionsAgentOutputParser()
        )
        self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False)
    
    def process_message(self, message: str) -> str:
        """사용자 메시지를 처리하고 응답을 반환합니다."""
        try:
            result = self.agent_executor.invoke({
                "input": message,
                "chat_history": self.chat_history
            })
            return result["output"]
        except Exception as e:
            return f"죄송해요. 오류가 발생했어요: {str(e)}"

def call_chatbot(messages: List[Dict[str, Any]]) -> str:
    """채팅봇을 호출하여 응답을 생성합니다."""
    try:
        chatbot = ScheduleChatbot()
        
        # 마지막 메시지 처리
        last_message = messages[-1]
        if isinstance(last_message, dict):
            message_content = last_message["content"]
        elif isinstance(last_message, HumanMessage):
            message_content = last_message.content
        else:
            return "죄송해요. 메시지 형식이 올바르지 않아요."
            
        return chatbot.process_message(message_content)
    except Exception as e:
        return "죄송해요. 문제가 발생했어요. 다시 시도해 주시겠어요?" 