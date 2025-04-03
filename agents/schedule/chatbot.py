import os
from datetime import datetime
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.utils.function_calling import convert_to_openai_function

from tools import get_user_schedule, add_reservation

class DateManager:
    """날짜 관련 유틸리티 클래스"""
    @staticmethod
    def get_formatted_date() -> tuple[str, datetime]:
        """현재 날짜를 형식화하여 반환합니다."""
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y년 %m월 %d일")
        return formatted_date, current_date

class PromptManager:
    """프롬프트 관리 클래스"""
    @staticmethod
    def load_system_prompt() -> str:
        """시스템 프롬프트를 로드합니다."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file_path = os.path.join(current_dir, "prompt_kr.txt")
        
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    @staticmethod
    def create_prompt_template(system_prompt: str) -> ChatPromptTemplate:
        """프롬프트 템플릿을 생성합니다."""
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

class ScheduleChatbot:
    """일정 관리 채팅봇 클래스"""
    def __init__(self):
        self._initialize_llm()
        self._initialize_tools()
        self._initialize_prompt()
        self._initialize_agent()
        self.chat_history = []
    
    def _initialize_llm(self) -> None:
        """LLM을 초기화합니다."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True
        )
    
    def _initialize_tools(self) -> None:
        """사용할 도구들을 초기화합니다."""
        self.tools = [get_user_schedule, add_reservation]
        self.functions = [convert_to_openai_function(t) for t in self.tools]
    
    def _initialize_prompt(self) -> None:
        """프롬프트를 초기화합니다."""
        system_prompt = PromptManager.load_system_prompt()
        formatted_date, _ = DateManager.get_formatted_date()
        system_prompt = f"오늘은 {formatted_date}입니다.\n\n{system_prompt}\n\n 예약은 오늘 이후의 날짜로만 가능해요."
        self.prompt = PromptManager.create_prompt_template(system_prompt)
    
    def _initialize_agent(self) -> None:
        """에이전트를 초기화합니다."""
        self.agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(x["intermediate_steps"]),
                "chat_history": lambda x: x["chat_history"]
            }
            | self.prompt
            | self.llm.bind(functions=self.functions)
            | OpenAIFunctionsAgentOutputParser()
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=False,
            return_intermediate_steps=False,
            max_iterations=5,
            max_execution_time=60,
            early_stopping_method="generate"
        )
    
    def process_message(self, message: str) -> str:
        """사용자 메시지를 처리하고 응답을 반환합니다."""
        try:
            result = self.agent_executor.invoke({
                "input": message,
                "chat_history": self.chat_history
            })
            
            self._update_chat_history(message, result["output"])
            return result["output"]
            
        except Exception as e:
            return self._handle_error(e)
    
    def _update_chat_history(self, message: str, response: str) -> None:
        """채팅 기록을 업데이트합니다."""
        self.chat_history.extend([
            HumanMessage(content=message),
            AIMessage(content=response)
        ])
    
    def _handle_error(self, error: Exception) -> str:
        """에러를 처리하고 적절한 메시지를 반환합니다."""
        if "maximum iterations" in str(error):
            return "죄송해요. 처리가 지연되고 있어요. 잠시 후에 다시 시도해 주시겠어요?"
        return f"오류가 발생했습니다: {str(error)}"

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